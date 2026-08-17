# cleanup_cache.ps1
# 작성: 2026-08-14 / Mavis
# 목적: 캐시/대용량 폴더 6개를 휴지통(Recycle Bin)으로 이동
# 안전: 영구 삭제 아님 — Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory + RecycleOption.SendToRecycleBin
# 실행: PowerShell (관리자 권장) 에서
#        powershell -NoProfile -ExecutionPolicy Bypass -File .\cleanup_cache.ps1

$ErrorActionPreference = 'Continue'

$targets = @(
    'C:\Users\Playdata\AppData\Local\uv',
    'C:\Users\Playdata\miniforge3',
    'C:\Users\Playdata\.local',
    'C:\Users\Playdata\.cache',
    'C:\Users\Playdata\Desktop\SKN28-FINAL-1Team\.venv-ml',
    'C:\Users\Playdata\AppData\Local\Packages'
)

try {
    Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
} catch {
    Write-Host "[FATAL] Microsoft.VisualBasic 로드 실패: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ">>> 6개 폴더 휴지통 이동 시작 (병렬, Start-Job)" -ForegroundColor Yellow
Write-Host ">>> 시작 시각: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Yellow
$startTime = Get-Date

$jobs = @()
foreach ($t in $targets) {
    $jobs += Start-Job -ScriptBlock {
        param($p)
        $start = Get-Date
        $before = 0L
        if (Test-Path $p) {
            try {
                $root = New-Object System.IO.DirectoryInfo $p
                foreach ($f in $root.EnumerateFiles('*', 'AllDirectories')) { $before += $f.Length }
            } catch { }
        }
        $beforeGB = [math]::Round($before / 1GB, 2)
        $err = $null
        try {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                $p,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
            )
        } catch {
            $err = $_.Exception.Message
        }
        $afterExists = Test-Path $p
        $elapsed = (Get-Date) - $start
        [PSCustomObject]@{
            Path        = $p
            BeforeGB    = $beforeGB
            StillExists = $afterExists
            ElapsedSec  = [math]::Round($elapsed.TotalSeconds, 1)
            Note        = if ($err) { "ERR: $err" } elseif ($afterExists) { '(일부 남음 — 시스템 점유/권한)' } else { 'TRASHED' }
        }
    } -ArgumentList $t
}

# 진행 상황 30초마다 출력
$reportEvery = 30
while ($jobs.State -contains 'Running') {
    Start-Sleep -Seconds $reportEvery
    $running = ($jobs | Where-Object State -eq 'Running').Count
    $done    = ($jobs | Where-Object State -eq 'Completed').Count
    $elapsed = [math]::Round((New-TimeSpan -Start $startTime -End (Get-Date)).TotalSeconds, 0)
    Write-Host ("  ... {0,4:F0}초 경과 / 완료 {1}/{2}" -f $elapsed, $done, $jobs.Count) -ForegroundColor DarkGray
}

$jobs | Wait-Job | Out-Null

Write-Host "`n=== 결과 ===" -ForegroundColor Cyan
$jobs | ForEach-Object { $_ | Receive-Job } | Format-Table -AutoSize -Wrap
$jobs | Remove-Job | Out-Null

$totalElapsed = [math]::Round((New-TimeSpan -Start $startTime -End (Get-Date)).TotalSeconds, 1)
Write-Host "`n총 소요: ${totalElapsed}초" -ForegroundColor Yellow

Write-Host "`n=== C드라이브 여유 공간 ===" -ForegroundColor Cyan
Get-PSDrive C -PSProvider FileSystem | ForEach-Object {
    [PSCustomObject]@{
        UsedGB  = [math]::Round($_.Used / 1GB, 2)
        FreeGB  = [math]::Round($_.Free / 1GB, 2)
        FreePct = [math]::Round($_.Free / ($_.Used + $_.Free) * 100, 2)
    }
} | Format-Table -AutoSize

Write-Host "`n완료. 휴지통에서 비우려면 수동으로 비워주세요 (Recycle Bin > Empty)." -ForegroundColor Green
