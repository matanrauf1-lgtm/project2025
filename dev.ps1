<#
.SYNOPSIS
  פיתוח מקומי של ISM-MICMAC על Windows, באותה תצורה שרצה ב-Streamlit Cloud דרך GitHub.

.EXAMPLE
  .\dev.ps1 setup   # פעם ראשונה: סביבת Python + קובץ secrets מקומי
  .\dev.ps1 run     # הרצת האפליקציה בדפדפן (http://localhost:8501)
  .\dev.ps1 check   # כל הבדיקות שרצות גם ב-GitHub Actions, לפני commit/push
  .\dev.ps1 share   # הרצה + קישור ציבורי זמני (Cloudflare Quick Tunnel) לגישה מרחוק, עד Ctrl+C
#>
param([ValidateSet('setup', 'run', 'check', 'share')][string]$Command = 'run')

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
# הסביבה מחוץ ל-OneDrive (אלפי קבצים שלא צריך לסנכרן) ומחוץ ל-AppData (ש-Python מ-Microsoft Store מפנה מחדש)
$Venv = Join-Path $env:USERPROFILE '.venvs\project2025'
$Py = Join-Path $Venv 'Scripts\python.exe'
$Secrets = Join-Path $Root '.streamlit\secrets.toml'
$LocalData = Join-Path $env:USERPROFILE '.ism_micmac'

function Ensure-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "יוצר סביבת Python ב-$Venv ..."
        python -m venv $Venv
    }
    & $Py -m pip install -q --upgrade pip
    & $Py -m pip install -q -r (Join-Path $Root 'requirements.txt') pytest
    if ($LASTEXITCODE) { throw 'התקנת התלויות נכשלה' }
}

function Ensure-Secrets {
    if (Test-Path $Secrets) { Write-Host "קובץ secrets מקומי קיים: $Secrets"; return }
    New-Item -ItemType Directory -Force (Split-Path $Secrets) | Out-Null
    New-Item -ItemType Directory -Force $LocalData | Out-Null
    $pass = -join ((48..57) + (97..122) | Get-Random -Count 14 | ForEach-Object { [char]$_ })
    $db = (Join-Path $LocalData 'ism_data.db') -replace '\\', '/'
    @"
# קובץ מקומי בלבד - מוחרג מ-Git (.gitignore). ב-Streamlit Cloud מגדירים את אותם מפתחות ב-Settings > Secrets.
ADMIN_USERNAME = "admin_ism"
ADMIN_PASSWORD = "$pass"
# מסד הנתונים המקומי מחוץ ל-OneDrive, כדי שהסנכרון לא ינעל את הקובץ בזמן כתיבה
ISM_DB_PATH = "$db"
# OPENROUTER_API_KEY = ""
# ANTHROPIC_API_KEY = ""
"@ | ForEach-Object { [IO.File]::WriteAllText($Secrets, $_, (New-Object Text.UTF8Encoding $false)) }  # TOML בלי BOM
    Write-Host "נוצר $Secrets"
    Write-Host "סיסמת מנהל מקומית: $pass  (אפשר לשנות בקובץ)"
}

function Find-Cloudflared {
    $c = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe")) {
        if (Test-Path $p) { return $p }
    }
    Write-Host 'מתקין cloudflared (Cloudflare) ...'
    winget install --id Cloudflare.cloudflared -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    foreach ($p in @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe")) {
        if (Test-Path $p) { return $p }
    }
    throw 'cloudflared לא נמצא. התקן ידנית: winget install Cloudflare.cloudflared'
}

function Test-AppUp {
    try { return (Invoke-WebRequest -UseBasicParsing 'http://localhost:8501/_stcore/health' -TimeoutSec 2).Content -eq 'ok' }
    catch { return $false }
}

switch ($Command) {
    'setup' {
        Ensure-Venv
        Ensure-Secrets
        Write-Host 'מוכן. להרצה: .\dev.ps1 run   לבדיקה: .\dev.ps1 check'
    }
    'run' {
        if (-not (Test-Path $Py)) { Ensure-Venv }
        if (-not (Test-Path $Secrets)) { Ensure-Secrets }
        Set-Location $Root
        & $Py -m streamlit run (Join-Path $Root 'project2025.py') --server.headless false
    }
    'check' {
        if (-not (Test-Path $Py)) { Ensure-Venv }
        Set-Location $Root
        Write-Host '1/3 בדיקת תחביר'
        & $Py -m py_compile project2025.py ism_core.py storage.py report_html.py
        if ($LASTEXITCODE) { throw 'שגיאת תחביר' }
        Write-Host '2/3 התאמת התלויות (pip check)'
        & $Py -m pip check
        if ($LASTEXITCODE) { throw 'יש התנגשות בין גרסאות התלויות' }
        Write-Host '3/3 pytest: ליבה מתמטית, מסד נתונים ובדיקת עשן של האפליקציה המלאה'
        & $Py -m pytest -q
        if ($LASTEXITCODE) { throw 'בדיקות נכשלו' }
        Write-Host 'הכל תקין - אפשר לעשות commit ו-push.' -ForegroundColor Green
    }
    'share' {
        if (-not (Test-Path $Py)) { Ensure-Venv }
        if (-not (Test-Path $Secrets)) { Ensure-Secrets }
        $cf = Find-Cloudflared
        $logDir = Join-Path $LocalData 'logs'
        New-Item -ItemType Directory -Force $logDir | Out-Null
        $started = @()
        try {
            if (Test-AppUp) {
                Write-Host 'האפליקציה כבר רצה על פורט 8501 - משתמש בה.'
            } else {
                Write-Host 'מפעיל את האפליקציה ...'
                $started += Start-Process -FilePath $Py -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
                    -ArgumentList '-m', 'streamlit', 'run', 'project2025.py', '--server.headless', 'true', '--server.port', '8501' `
                    -RedirectStandardOutput (Join-Path $logDir 'app.out.log') -RedirectStandardError (Join-Path $logDir 'app.err.log')
                for ($i = 0; $i -lt 60 -and -not (Test-AppUp); $i++) { Start-Sleep 1 }
                if (-not (Test-AppUp)) { throw "האפליקציה לא עלתה. ראה $logDir\app.err.log" }
            }

            Write-Host 'פותח מנהרה ציבורית (Cloudflare Quick Tunnel) ...'
            $tunnelLog = Join-Path $logDir 'tunnel.log'
            Remove-Item $tunnelLog -ErrorAction SilentlyContinue
            $started += Start-Process -FilePath $cf -WindowStyle Hidden -PassThru `
                -ArgumentList 'tunnel', '--no-autoupdate', '--url', 'http://localhost:8501' `
                -RedirectStandardError $tunnelLog -RedirectStandardOutput (Join-Path $logDir 'tunnel.out.log')
            $url = $null
            for ($i = 0; $i -lt 60 -and -not $url; $i++) {
                Start-Sleep 1
                if (Test-Path $tunnelLog) {
                    $m = Select-String -Path $tunnelLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1
                    if ($m) { $url = $m.Matches[0].Value }
                }
            }
            if (-not $url) { throw "המנהרה לא נפתחה. ראה $tunnelLog" }
            # Cloudflare רושם את הכתובת ב-DNS תוך כמה שניות; מחכים שהקישור באמת יענה לפני שמציגים אותו
            for ($i = 0; $i -lt 30; $i++) {
                try { if ((Invoke-WebRequest -UseBasicParsing "$url/_stcore/health" -TimeoutSec 5).Content -eq 'ok') { break } } catch {}
                Start-Sleep 2
            }
            try { Set-Clipboard $url } catch {}
            Write-Host ''
            Write-Host "קישור ציבורי (הועתק ללוח): $url" -ForegroundColor Green
            Write-Host 'שלח אותו רק למי שמורשה. הקישור פעיל כל עוד החלון הזה פתוח והמחשב מחובר ולא במצב שינה.'
            Write-Host 'הקישור משתנה בכל הפעלה. לעצירה: Ctrl+C'
            while ($true) {
                Start-Sleep 5
                if ($started | Where-Object { $_.HasExited }) { throw 'אחד התהליכים נעצר. בדוק את הלוגים ב-' + $logDir }
            }
        } finally {
            foreach ($p in $started) { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
            Write-Host 'השיתוף הופסק.'
        }
    }
}
