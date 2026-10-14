# HybridSwingNet (stockxpert) - reproducible environment setup
#
# Run from the repository root:
#     powershell -ExecutionPolicy Bypass -File hybrid_swingnet\setup_env.ps1
#
# IT NEVER TOUCHES .\env (the live production venv). Nothing is installed into it.
#
# TWO SUPPORTED PATHS
# -------------------
# PATH A (default, no installs at all): run the vendored code with the EXISTING
#   production interpreter. We verified that .\env already contains everything the
#   core V3 model + dataset path needs (torch, numpy, pandas, scikit-learn, PyYAML,
#   scipy). This is what test_hybrid_swingnet.py and run_oos.py use. Because this
#   only *reads* the interpreter and puts hybrid_swingnet\upstream\src on
#   sys.path, it is not a modification of the production environment.
#
# PATH B (isolation): create a SEPARATE virtual environment at
#   hybrid_swingnet\.venv and install the vendored requirements.txt there. Use
#   this if you want the full upstream toolchain (matplotlib/seaborn/transformers)
#   or the authors' own scripts. Upstream pins Python 3.13 in .python-version;
#   we checked that every requirement also has a Python 3.14 wheel, so either
#   interpreter works. The script prefers 3.13 when available, via `uv`.

param(
    [switch]$PathB,          # create the separate venv and install requirements
    [string]$PythonExe = ""  # override the interpreter used for -PathB
)

$ErrorActionPreference = "Stop"
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$VendorDir  = Join-Path $PSScriptRoot "upstream"
$VenvDir    = Join-Path $PSScriptRoot ".venv"
$ProdPython = Join-Path $RepoRoot "env\Scripts\python.exe"

function Write-Head($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }

Write-Head "HybridSwingNet setup"
Write-Host "repo root     : $RepoRoot"
Write-Host "vendor dir    : $VendorDir"
Write-Host "production env: $ProdPython  (NEVER modified by this script)"

if (-not (Test-Path (Join-Path $VendorDir "src\stockxpert"))) {
    throw "Vendored source not found at $VendorDir\src\stockxpert - re-vendor the upstream commit first."
}

# ---------------------------------------------------------------------------
# PATH A - verify the existing production interpreter can run the vendored core
# ---------------------------------------------------------------------------
Write-Head "PATH A - check the existing production interpreter (no installs)"
if (-not (Test-Path $ProdPython)) {
    Write-Host "production interpreter not found at $ProdPython" -ForegroundColor Yellow
} else {
    & $ProdPython -c @"
import importlib, sys
print('python', sys.version.split()[0])
missing = []
for name in ('numpy','pandas','sklearn','torch','yaml','scipy'):
    try:
        mod = importlib.import_module(name)
        print(f'  OK   {name:10s} {getattr(mod, \"__version__\", \"?\")}')
    except Exception as exc:
        print(f'  MISS {name:10s} {type(exc).__name__}')
        missing.append(name)
soft = []
for name in ('matplotlib','seaborn','transformers','sentencepiece'):
    try:
        importlib.import_module(name); print(f'  OK   {name:10s} (optional)')
    except Exception:
        soft.append(name)
print()
if missing:
    print('PATH A INCOMPLETE - missing core deps:', ', '.join(missing))
    print('Use -PathB to build an isolated environment instead.')
else:
    print('PATH A READY - you can run:')
    print('  .\\env\\Scripts\\python.exe test_hybrid_swingnet.py')
    print('  .\\env\\Scripts\\python.exe -m hybrid_swingnet.run_oos --max-symbols 20 --epochs 2')
if soft:
    print('optional extras not installed (only needed by upstream plot/release scripts):', ', '.join(soft))
"@
}

# ---------------------------------------------------------------------------
# PATH B - separate isolated venv
# ---------------------------------------------------------------------------
if (-not $PathB) {
    Write-Head "Skipping PATH B"
    Write-Host "Re-run with -PathB to create an isolated venv at $VenvDir"
    exit 0
}

Write-Head "PATH B - create isolated venv at $VenvDir"
if (Test-Path $VenvDir) {
    Write-Host "venv already exists, reusing: $VenvDir"
} else {
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    $py313 = $null
    try { $py313 = (& py -3.13 -c "import sys;print(sys.executable)" 2>$null) } catch { $py313 = $null }

    if ($uv -and $PythonExe -eq "") {
        $target = if ($py313) { $py313 } else { "3.14" }
        Write-Host "using uv with python: $target"
        & uv venv --python $target $VenvDir
    } else {
        $base = if ($PythonExe -ne "") { $PythonExe } elseif ($py313) { $py313 } else { "python" }
        Write-Host "using $base -m venv"
        & $base -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
Write-Host "venv python: $VenvPython"

Write-Head "Installing vendored requirements.txt (this downloads ~1 GB: torch)"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $VendorDir "requirements.txt")

Write-Head "Installing the vendored package in editable mode"
& $VenvPython -m pip install -e $VendorDir

Write-Head "PATH B done"
Write-Host "Run the isolated copies with:"
Write-Host "  `"$VenvPython`" test_hybrid_swingnet.py"
Write-Host "  `"$VenvPython`" -m hybrid_swingnet.run_oos --max-symbols 20 --epochs 2"
Write-Host ""
Write-Host "NOTE: run_oos.py / test_hybrid_swingnet.py put the vendor on sys.path themselves,"
Write-Host "      so they work under EITHER interpreter without the editable install."
