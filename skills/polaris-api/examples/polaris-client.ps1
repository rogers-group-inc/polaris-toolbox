# Minimal Polaris API client for PowerShell 7+. Dot-source, then:
#   $env:POLARIS_URL = 'https://polaris.example.com'; $env:POLARIS_TOKEN = 'polaris_...'
#   Invoke-Polaris GET '/assets' -Query @{ search = 'fw-'; limit = 25 }
#   Get-PolarisAll '/events' -Key events -Query @{ level = 'warning,error' }
#
# Conventions: bearer on every call, { error } envelope surfaced as the exception message,
# page with `total`, back off and retry on 429.

function Invoke-Polaris {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('GET','POST','PUT','DELETE')][string]$Method,
        [Parameter(Mandatory)][string]$Path,
        [hashtable]$Query,
        [object]$Body,
        [string]$BaseUrl = $env:POLARIS_URL,
        [string]$Token = $env:POLARIS_TOKEN,
        [int]$MaxRetries = 3
    )
    if (-not $BaseUrl -or -not $Token) { throw 'Set POLARIS_URL and POLARIS_TOKEN (or pass -BaseUrl / -Token).' }
    $uri = $BaseUrl.TrimEnd('/') + '/api/v1' + $Path
    if ($Query) {
        $qs = ($Query.GetEnumerator() | Where-Object { $null -ne $_.Value } | ForEach-Object { "$([uri]::EscapeDataString($_.Key))=$([uri]::EscapeDataString([string]$_.Value))" }) -join '&'
        if ($qs) { $uri += '?' + $qs }
    }
    $headers = @{ Authorization = "Bearer $Token" }
    for ($attempt = 0; ; $attempt++) {
        try {
            $params = @{ Method = $Method; Uri = $uri; Headers = $headers; ErrorAction = 'Stop' }
            if ($null -ne $Body) { $params.ContentType = 'application/json'; $params.Body = ($Body | ConvertTo-Json -Depth 10) }
            return Invoke-RestMethod @params
        } catch {
            $resp = $_.Exception.Response
            $status = if ($resp) { [int]$resp.StatusCode } else { 0 }
            if ($status -eq 429 -and $attempt -lt $MaxRetries) {
                $wait = 0; try { $wait = [int]$resp.Headers.GetValues('Retry-After')[0] } catch {}
                if ($wait -le 0) { $wait = [math]::Pow(2, $attempt) }
                Start-Sleep -Seconds $wait; continue
            }
            $msg = $null
            try { $msg = ($_.ErrorDetails.Message | ConvertFrom-Json).error } catch {}
            throw "Polaris $Method $Path -> $status $($msg ?? $_.Exception.Message)"
        }
    }
}

function Get-PolarisAll {
    # Drain a paged list ({ <Key>: [...], total }) using total, never .Count of one page.
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Key, [hashtable]$Query = @{}, [int]$Limit = 200)
    $offset = 0
    do {
        $q = $Query.Clone(); $q.limit = $Limit; $q.offset = $offset
        $page = Invoke-Polaris GET $Path -Query $q
        $items = @($page.$Key)
        $items
        $offset += $items.Count
    } while ($items.Count -gt 0 -and $offset -lt $page.total)
}

function Invoke-PolarisQuarantine {
    # SIEM flow: preflight -> find by MAC/IP/hostname -> quarantine. Returns the per-FortiGate targets.
    param([Parameter(Mandatory)][string]$Identifier, [Parameter(Mandatory)][string]$Reason)
    $avail = Invoke-Polaris GET '/assets/quarantine-availability'
    if (-not $avail.pushEnabled) { throw 'quarantine push is not enabled on any integration' }
    $found = Invoke-Polaris GET '/assets' -Query @{ search = $Identifier; limit = 5 }
    if ($found.total -ne 1) { throw "expected exactly one asset for $Identifier, found $($found.total)" }
    Invoke-Polaris POST "/assets/$($found.assets[0].id)/quarantine" -Body @{ reason = $Reason }
}
