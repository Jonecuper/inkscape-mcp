# Inkscape MCP — идемпотентная установка/подключение (Windows 10/11)
# Использование: powershell -NoProfile -ExecutionPolicy Bypass -File setup.ps1 [-TargetDir C:\dev\tools\inkscape-mcp]
# Повторный запуск безопасен: определяет уже существующий клон/конфиг и чинит недостающее.
param(
    [string]$TargetDir = "$env:USERPROFILE\inkscape-mcp",
    [string]$Repo = "https://github.com/sandraschi/inkscape-mcp"
)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8 } catch {}
function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }

# 0. Пререквизиты
Step "Проверка пререквизитов"
$missing = @()
foreach ($t in "git","uv") { if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { $missing += $t } }
if ($missing) { throw "Не найдено: $($missing -join ', '). Установите (winget install --id astral-sh.uv / Git.Git) и повторите." }
$inkscape = Get-Command inkscape -ErrorAction SilentlyContinue
if (-not $inkscape) {
    Write-Warning "Inkscape не найден в PATH. Рисование/анимация будут работать, экспорт/конверт — нет."
    Write-Warning "Установите: winget install --id Inkscape.Inkscape --exact --source winget"
} else { Write-Host "Inkscape: $((inkscape --version) -split "`n")[0]" }

# 1. Клон
Step "Клон/обновление в $TargetDir"
if (Test-Path "$TargetDir\.git") {
    git -C $TargetDir pull --ff-only 2>&1 | Select-Object -Last 1
} else {
    New-Item -ItemType Directory -Force -Path (Split-Path $TargetDir) | Out-Null
    git clone --depth 1 $Repo "$TargetDir"
}

# 2. Check
Step "Проверка окружения (-Check)"
& cmd /c "`"$TargetDir\start.bat`" -Check -Json" 2>$null | Tee-Object -Variable checkRaw | Out-Null
$raw = ($checkRaw -join "`n")
$json = $raw.Substring($raw.IndexOf('{'), $raw.LastIndexOf('}') - $raw.IndexOf('{') + 1)
$check = $json | ConvertFrom-Json
Write-Host "verdict: $($check.verdict)"
foreach ($c in $check.checks) { Write-Host ("  {0,-14} {1,-8} {2}" -f $c.name, $c.status, $c.detail) }
if ($check.verdict -like "BLOCKED*") { throw "BLOCKED: $($check.verdict)" }

# 3. Install (если ещё не стоит)
if (-not (Test-Path "$TargetDir\.venv")) {
    Step "Установка зависимостей (-Yes -NoStart, 2-4 мин, не прерывать)"
    & cmd /c "`"$TargetDir\start.bat`" -Yes -NoStart"
    if ($LASTEXITCODE -ne 0) { throw "start.bat -Yes -NoStart завершился с кодом $LASTEXITCODE (см. $TargetDir\logs\start.log)" }
} else { Step "Виртуальное окружение уже есть — установку пропускаю" }

# 4. Подключение к Claude Code (идемпотентно)
Step "Подключение MCP-сервера к Claude Code"
$dir = (Resolve-Path $TargetDir).Path
$existing = ((claude mcp get inkscape 2>&1) -join "`n")
$existingN = ($existing -replace '\\', '/').ToLower()
$dirN = ($dir -replace '\\', '/').ToLower()
if ($existing -notmatch "not found|error" -and $existingN.Contains($dirN)) {
    Write-Host "Сервер 'inkscape' уже настроен на $dir"
} else {
    if ($existing -notmatch "not found|error") { claude mcp remove inkscape --scope user 2>&1 | Out-Null }
    claude mcp add inkscape --scope user -- uv --directory $dir run inkscape-mcp --mode stdio
}

# 5. Verification
Step "Healthcheck"
claude mcp list 2>&1 | Select-String "inkscape"

Write-Host "`nГотово. Перезапустите сессию Claude Code, чтобы появились mcp__inkscape__* тулы." -ForegroundColor Green
Write-Host "Дашборд (опционально): `"$TargetDir\start.bat`" -Yes -Detach -NoBrowser  -> http://127.0.0.1:11029"
