# 🤖 Cost Estimator AI Agent

A comprehensive, production-ready AI platform designed specifically for the **fabrication, EPC, structural steel, and piping industries**. This agent automates the complex journey from raw engineering documents to professional commercial quotations.

---

## 📖 Table of Contents
1. [Project Overview](#project-overview)
2. [How It Works (Process Workflow)](#how-it-works-process-workflow)
3. [Core Features & Features Guide](#core-features--features-guide)
4. [Technical Implementation](#technical-implementation)
5. [Installation & Setup](#installation--setup)
6. [Testing Guide (Step-by-Step)](#testing-guide-step-by-step)
7. [API Documentation](#api-documentation)

---

## 🏗 Project Overview

Estimating costs for industrial fabrication is traditionally a bottleneck. Engineers spend hours manually reading drawings and BOQs, then calculating weights and costs in isolated spreadsheets. 

This platform bridges that gap by using **AI for data extraction** and a **deterministic engine for calculation**, ensuring that while the discovery is automated, the costing logic remains 100% transparent and consistent.

---

## ⚙️ How It Works (Process Workflow)

The agent follows an industry-standard estimation pipeline:

1.  **Ingestion**: User uploads multiple engineering documents (GA drawings, Detail drawings, Excel BOQs, or even photos of sketches).
2.  **AI Extraction (The "Reader")**: The agent uses Multi-modal AI (Groq Vision) to "see" the drawings and "read" the BOQs. It extracts dimensions (L, W, T, OD), member types, material grades, and fabrication annotations.
3.  **Human-in-the-Loop Confirmation**: The user reviews the extracted data. Flags highlight low-confidence items where the AI might be unsure, ensuring zero-error propagation.
4.  **Deterministic Costing (The "Engine")**: Once confirmed, the Python costing engine takes over. It calculates weights using standard engineering density and then applies configurable rates for materials, fabrication hours, welding joints, and surface treatments.
5.  **Professional Output**: The system generates a high-fidelity Excel sheet with **preserved formulas** and an AI-drafted **Cover Letter** that includes standard fabrication exclusions and contractual protections.

---

## 🌟 Core Features & Features Guide

### 1. Dashboard (The Nerve Center)
- **What it does**: Provides a bird's-eye view of your estimation department.
- **Workflow**: Displays trend charts of quoted values, recent job statuses, and quick-access buttons to all tools.
- **Example**: Check the "Quotation Trend" to see if your hit rate or bid volume is increasing.

### 2. New Estimate (End-to-End Workflow)
- **What it does**: The flagship module for generating a complete quote.
- **Workflow**: 
    - **Step 1 (Upload)**: Drag & drop your PDF drawings and BOQ.
    - **Step 2 (Extract)**: AI processes files (takes ~15-30s).
    - **Step 3 (Confirm)**: Review and Edit the extracted table. Flagged items appear in orange.
    - **Step 4 (Result)**: Instantly view the cost breakdown and download the Excel sheet.

### 3. Drawing Reader (Quick Extraction)
- **What it does**: A standalone tool to extract engineering data from a single drawing without creating a full job.
- **Example**: Upload a GA drawing of a pipe rack. The AI will output a table of all columns, beams, and bracing members found.

### 4. Weight Calculator (Precision Tool)
- **What it does**: A deterministic calculator for various steel sections (Plate, Pipe, Round Bar, Angle, Flat Bar).
- **Process**: Uses the density of steel (7850 kg/m³) to provide exact weights.
- **Example**: Enter `Pipe: 200mm OD, 10mm Thickness, 6000mm Length`. It will output the weight and the exact formula used.

### 5. BOQ Parser (Excel/PDF Cleaner)
- **What it does**: Parses messy client BOQs into structured data.
- **Workflow**: Upload a client Excel file with non-standard formatting. The AI mapping identifies tags, descriptions, and quantities.

### 6. Excel Generator (The Final Output)
- **What it does**: Generates a professional `.xlsx` file.
- **Process**: Unlike simple CSV exports, this uses `openpyxl` to create a workbook with 4 sheets:
    - **Job Summary**: Branding and final totals.
    - **Costing Sheet**: Detailed line items with **live Excel formulas**.
    - **Rates Config**: The rates used for that specific job.
    - **Audit Trail**: Step-by-step log of how the AI reached its conclusions.

### 7. Quote Summary (Visual Analytics)
- **What it does**: Provides a visual breakdown of costs (Material vs. Labor vs. Consumables).
- **Feature**: Uses interactive pie charts to help engineers spot where the most expensive part of the project lies.

### 8. Cover Letter (Commercial Draft)
- **What it does**: Uses AI to draft a professional cover letter from the client's quotation.
- **Workflow**: Upload the client's RFQ document. The AI extracts payment terms, delivery terms, and the scope of work, then drafts a letter including master fabrication clauses (exclusions, AFC drawing responsibility, etc.).

---

## 🛠 Technical Implementation

### Backend Architecture
- **API**: Built with **FastAPI** for high-performance async processing.
- **AI Integration**: Uses **Instructor** for structured data extraction and **Groq** for ultra-fast processing.
- **Calculation Engines**: Modular Python services for each cost component (e.g., `welding_cost.py`, `surface_treatment.py`).
- **Database**: **SQLAlchemy** with `aiosqlite` for local development. Handles 10+ relational tables for full auditability.
- **Reporting**: uses `openpyxl` for Excel and `ReportLab` for PDF.

### Frontend Architecture
- **Framework**: **React 19** with **TypeScript** for type-safe state management.
- **Styling**: Vanilla CSS design system optimized for premium light-mode aesthetics.
- **State Management**: **Zustand** for lightweight global states.
- **API Client**: **Axios** with global interceptors for error handling.

---

## 🚀 Installation & Setup

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL 14+** (recommended for production) or SQLite (for development)

### Quick Start (3 Options)

#### Option 1: Quick Setup Script (Windows - Recommended)
```powershell
cd backend
.\setup_db.ps1
```
This script will:
- Create PostgreSQL database
- Set up environment variables
- Install Python dependencies
- Initialize database with seed data

#### Option 2: Manual Setup with PostgreSQL

1.  **Install PostgreSQL**:
    ```powershell
    # Windows (Chocolatey)
    choco install postgresql
    
    # macOS
    brew install postgresql
    
    # Ubuntu/Debian
    sudo apt install postgresql postgresql-contrib
    ```

2.  **Create Database**:
    ```sql
    psql -U postgres
    CREATE DATABASE cost_estimator;
    \q
    ```

3.  **Backend Setup**:
    ```bash
    cd backend
    pip install -r requirements.txt
    
    # Copy environment file
    copy .env.example .env  # Windows
    # OR
    cp .env.example .env    # Linux/macOS
    
    # Update .env with your PostgreSQL credentials:
    # DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/cost_estimator
    # Add your GROQ_API_KEY
    
    # Initialize database
    python init_db.py init
    
    # Start server
    uvicorn app.main:app --reload
    ```

4.  **Frontend Setup**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

#### Option 3: Development Setup with SQLite

1.  **Backend Setup**:
    ```bash
    cd backend
    pip install -r requirements.txt
    
    # Copy environment file
    copy .env.example .env
    
    # Update .env to use SQLite:
    # DATABASE_URL=sqlite+aiosqlite:///./cost_estimator.db
    # Add your GROQ_API_KEY
    
    # Initialize database
    python init_db.py init
    
    # Start server
    python -m uvicorn app.main:app --reload
    ```

2.  **Frontend Setup**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

### Database Management Commands

```powershell
# Initialize database (create tables + seed data)
python init_db.py init

# Reset database (drop + create + seed)
python init_db.py reset

# Test database connection
python init_db.py test

# Run database migrations (Alembic)
alembic upgrade head

# Generate new migration
alembic revision --autogenerate -m "description"
```

### Configuration

Edit `backend/.env` to configure:
- **Database**: PostgreSQL or SQLite connection
- **AI Provider**: Groq or Anthropic API keys
- **Storage**: Local, Azure, or AWS S3
- **Company Branding**: Name, address, signatory details
- **Connection Pooling**: Pool size and timeout settings

For detailed database setup instructions, see [backend/DATABASE_SETUP.md](backend/DATABASE_SETUP.md).

---

## 🧪 Testing Guide (Step-by-Step)

To verify the agent is working correctly, follow this test plan:

### Test 1: Health Check
- Open your browser to `http://localhost:8000/health`.
- **Expected Result**: `{"status": "ok", "version": "1.0.0"}`.

### Test 2: Rate Configuration (Crucial)
1. Navigate to the **Settings** page in the UI.
2. Click **Seed Defaults** to populate the database with fabrication rates.
3. Edit the "Material Rate per kg" and save.
- **Expected Result**: "Rates saved successfully" toast appears.

### Test 3: Weight Calculation (Deterministic Test)
1. Go to **Weight Calculator**.
2. Select **Plate**, enter `1000mm x 1000mm x 10mm`, Qty `1`.
3. Click **Calculate**.
- **Expected Result**: Should show exactly `78.5000 kg`.

### Test 4: End-to-End Estimation (The Big Test)
1. Go to **New Estimate**.
2. Upload a sample technical drawing or BOQ.
3. Click **Start AI Extraction**.
4. Confirm the extracted data in Step 3.
5. Review the final **Selling Price**.
6. Download the **Excel Sheet** and open it.
- **Expected Result**: Excel should contain the same totals as the UI and include living formulas in Sheet 2.

### Test 5: AI Assistant
1. Click the **Bot icon** in the bottom right.
2. Ask: "How do you calculate welding cost?"
- **Expected Result**: AI should reply explaining the joint-based calculation method using your configured rates.

---

## 📑 API Documentation

Once the backend is running, you can explore the full Interactive Swagger documentation at:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

| Endpoint | Method | Description |
|---|---|---|
| `/api/estimate/upload` | POST | Create job & upload files |
| `/api/estimate/extract` | POST | Trigger AI extraction |
| `/api/estimate/calculate` | POST | Run costing engine |
| `/api/cover-letter/generate` | POST | Generate PDF cover letter |
| `/api/settings/` | GET/PUT | Manage fabrication rates |

---
*Built for excellence in fabrication engineering.*
#   C o s t E s t i m a t o r A g e n t 
 
 #   C o s t E s t i m a t o r A g e n t 
 
 #   C o s t E s t i m a t o r A g e n t 
 
 