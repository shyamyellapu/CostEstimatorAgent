# PostgreSQL Database Setup Script
# This script helps set up PostgreSQL for the Cost Estimator application

param(
    [Parameter(Mandatory=$false)]
    [string]$Action = "setup",
    
    [Parameter(Mandatory=$false)]
    [string]$DBName = "cost_estimator",
    
    [Parameter(Mandatory=$false)]
    [string]$DBUser = "postgres",
    
    [Parameter(Mandatory=$false)]
    [string]$DBPassword = "",
    
    [Parameter(Mandatory=$false)]
    [string]$DBHost = "localhost",
    
    [Parameter(Mandatory=$false)]
    [int]$DBPort = 5432
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Message {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Test-PostgreSQL {
    Write-Step "Checking PostgreSQL installation..."
    
    try {
        $psqlVersion = & psql --version 2>&1
        Write-Success "PostgreSQL is installed: $psqlVersion"
        return $true
    }
    catch {
        Write-Error-Message "PostgreSQL is not installed or not in PATH"
        Write-Host "`nTo install PostgreSQL:"
        Write-Host "1. Download from https://www.postgresql.org/download/windows/"
        Write-Host "2. Or use Chocolatey: choco install postgresql"
        return $false
    }
}

function Create-Database {
    Write-Step "Creating database '$DBName'..."
    
    # Build connection string
    $env:PGPASSWORD = $DBPassword
    
    try {
        # Check if database exists
        $checkDb = & psql -U $DBUser -h $DBHost -p $DBPort -lqt 2>&1 | Select-String -Pattern "^\s*$DBName\s*\|"
        
        if ($checkDb) {
            Write-Host "Database '$DBName' already exists" -ForegroundColor Yellow
            $response = Read-Host "Do you want to drop and recreate it? (yes/no)"
            
            if ($response -eq "yes") {
                Write-Step "Dropping existing database..."
                & psql -U $DBUser -h $DBHost -p $DBPort -c "DROP DATABASE IF EXISTS $DBName;" 2>&1 | Out-Null
                Write-Success "Database dropped"
            }
            else {
                Write-Host "Keeping existing database" -ForegroundColor Yellow
                return
            }
        }
        
        # Create database
        & psql -U $DBUser -h $DBHost -p $DBPort -c "CREATE DATABASE $DBName;" 2>&1 | Out-Null
        Write-Success "Database '$DBName' created successfully"
    }
    catch {
        Write-Error-Message "Failed to create database: $_"
        throw
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Test-DatabaseConnection {
    Write-Step "Testing database connection..."
    
    $env:PGPASSWORD = $DBPassword
    
    try {
        & psql -U $DBUser -h $DBHost -p $DBPort -d $DBName -c "SELECT 1;" 2>&1 | Out-Null
        Write-Success "Database connection successful"
    }
    catch {
        Write-Error-Message "Failed to connect to database: $_"
        throw
    }
    finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Setup-Environment {
    Write-Step "Setting up environment file..."
    
    if (Test-Path ".env") {
        Write-Host ".env file already exists" -ForegroundColor Yellow
        $response = Read-Host "Do you want to update the DATABASE_URL? (yes/no)"
        
        if ($response -ne "yes") {
            Write-Host "Skipping .env update" -ForegroundColor Yellow
            return
        }
    }
    else {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Success "Copied .env.example to .env"
        }
        else {
            Write-Error-Message ".env.example not found"
            return
        }
    }
    
    # Build database URL
    $dbUrl = "postgresql+asyncpg://${DBUser}:${DBPassword}@${DBHost}:${DBPort}/${DBName}"
    
    # Update .env file
    $envContent = Get-Content ".env" -Raw
    
    if ($envContent -match "DATABASE_URL=") {
        $envContent = $envContent -replace "DATABASE_URL=.*", "DATABASE_URL=$dbUrl"
    }
    else {
        $envContent = "DATABASE_URL=$dbUrl`n" + $envContent
    }
    
    $envContent | Set-Content ".env" -NoNewline
    Write-Success "Updated DATABASE_URL in .env"
}

function Install-Dependencies {
    Write-Step "Installing Python dependencies..."
    
    # Check if virtual environment exists
    if (-not (Test-Path ".venv")) {
        Write-Host "Virtual environment not found. Creating..." -ForegroundColor Yellow
        python -m venv .venv
        Write-Success "Virtual environment created"
    }
    
    # Activate virtual environment
    & .venv\Scripts\Activate.ps1
    
    # Install requirements
    pip install -r requirements.txt
    Write-Success "Dependencies installed"
}

function Initialize-Database {
    Write-Step "Initializing database schema..."
    
    # Activate virtual environment
    & .venv\Scripts\Activate.ps1
    
    # Run init script
    python init_db.py init
    Write-Success "Database initialized"
}

function Show-Usage {
    Write-Host @"

PostgreSQL Database Setup Script
=================================

Usage:
    .\setup_db.ps1 [-Action <action>] [-DBName <name>] [-DBUser <user>] [-DBPassword <pass>]

Actions:
    setup       - Full setup (create DB, setup env, install deps, initialize)
    create      - Create database only
    init        - Initialize database schema only
    test        - Test database connection
    help        - Show this help message

Parameters:
    -DBName       Database name (default: cost_estimator)
    -DBUser       Database user (default: postgres)
    -DBPassword   Database password (default: prompt)
    -DBHost       Database host (default: localhost)
    -DBPort       Database port (default: 5432)

Examples:
    # Full setup with prompts
    .\setup_db.ps1

    # Create database only
    .\setup_db.ps1 -Action create -DBPassword "mypassword"

    # Test connection
    .\setup_db.ps1 -Action test -DBPassword "mypassword"

"@
}

# Main execution
try {
    Write-Host @"

╔═══════════════════════════════════════════════════════════╗
║        Cost Estimator - Database Setup Script            ║
╚═══════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

    if ($Action -eq "help") {
        Show-Usage
        exit 0
    }

    # Prompt for password if not provided
    if ([string]::IsNullOrEmpty($DBPassword)) {
        $securePassword = Read-Host "Enter PostgreSQL password for user '$DBUser'" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        $DBPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    }

    # Test PostgreSQL installation
    if (-not (Test-PostgreSQL)) {
        exit 1
    }

    switch ($Action) {
        "setup" {
            Create-Database
            Test-DatabaseConnection
            Setup-Environment
            Install-Dependencies
            Initialize-Database
            
            Write-Host @"

╔═══════════════════════════════════════════════════════════╗
║              Database Setup Complete! ✓                   ║
╚═══════════════════════════════════════════════════════════╝

Next steps:
1. Update API keys in .env file (GROQ_API_KEY, etc.)
2. Start the application:
   cd backend
   uvicorn app.main:app --reload

3. Open http://localhost:8000/docs for API documentation

"@ -ForegroundColor Green
        }
        
        "create" {
            Create-Database
            Test-DatabaseConnection
        }
        
        "init" {
            Test-DatabaseConnection
            Initialize-Database
        }
        
        "test" {
            Test-DatabaseConnection
        }
        
        default {
            Write-Error-Message "Unknown action: $Action"
            Show-Usage
            exit 1
        }
    }
}
catch {
    Write-Error-Message "Setup failed: $_"
    exit 1
}
