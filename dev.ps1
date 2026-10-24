<#
.SYNOPSIS
  פיתוח מקומי של ISM-MICMAC על Windows, באותה תצורה שרצה ב-Streamlit Cloud דרך GitHub.

.EXAMPLE
  .\dev.ps1 setup   # פעם ראשונה: סביבת Python + קובץ secrets מקומי
  .\dev.ps1 run     # הרצת האפליקציה בדפדפן (http://localhost:8501)
  .\dev.ps1 check   # כל הבדיקות שרצות גם ב-GitHub Actions, לפני commit/push
#>
param([ValidateSet('setup', 'run', 'check')][string]$Command = 'run')

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
        & $Py -m py_compile project2025.py ism_core.py storage.py
        if ($LASTEXITCODE) { throw 'שגיאת תחביר' }
        Write-Host '2/3 התאמת התלויות (pip check)'
        & $Py -m pip check
        if ($LASTEXITCODE) { throw 'יש התנגשות בין גרסאות התלויות' }
        Write-Host '3/3 pytest: ליבה מתמטית, מסד נתונים ובדיקת עשן של האפליקציה המלאה'
        & $Py -m pytest -q
        if ($LASTEXITCODE) { throw 'בדיקות נכשלו' }
        Write-Host 'הכל תקין - אפשר לעשות commit ו-push.' -ForegroundColor Green
    }
}
