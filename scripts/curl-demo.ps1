# Requires PowerShell 5+
# Usage: .\scripts\curl-demo.ps1

function Invoke-JsonCurl {
    param(
        [Parameter(Mandatory)]
        [string]$Method,
        [Parameter(Mandatory)]
        [string]$Url,
        [Parameter()]
        [string]$Json
    )

    if ($Json) {
        Write-Host "\n> curl -X $Method $Url -H 'Content-Type: application/json' -d '$Json'" -ForegroundColor Cyan
        curl.exe -sS -X $Method $Url -H "Content-Type: application/json" -d $Json | Write-Host
    }
    else {
        Write-Host "\n> curl -X $Method $Url" -ForegroundColor Cyan
        curl.exe -sS -X $Method $Url | Write-Host
    }
}

$baseUrl = "http://localhost:8080"

# Single event
$eventJson = '{"topic":"orders","event_id":"evt-1","timestamp":"2025-10-24T10:00:00Z","source":"publisher","payload":{"order_id":1}}'
Invoke-JsonCurl -Method "POST" -Url "$baseUrl/publish" -Json $eventJson

# Batch with duplicate
$batchJson = '[{"topic":"orders","event_id":"evt-1","timestamp":"2025-10-24T10:01:00Z","source":"publisher","payload":{"order_id":1}},{"topic":"orders","event_id":"evt-2","timestamp":"2025-10-24T10:02:00Z","source":"publisher","payload":{"order_id":2}},{"topic":"orders","event_id":"evt-1","timestamp":"2025-10-24T10:03:00Z","source":"publisher","payload":{"note":"duplicate"}}]'
Invoke-JsonCurl -Method "POST" -Url "$baseUrl/publish" -Json $batchJson

# Stats and events
Invoke-JsonCurl -Method "GET" -Url "$baseUrl/stats"
Invoke-JsonCurl -Method "GET" -Url "$baseUrl/events"
Invoke-JsonCurl -Method "GET" -Url "$baseUrl/events?topic=orders"
