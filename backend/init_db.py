"""Database initialization and management utilities."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import Base, engine
from app.models import RateConfiguration


async def create_database():
    """Create database tables."""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created successfully")


async def drop_database():
    """Drop all database tables."""
    print("Dropping database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("✓ Database tables dropped successfully")


async def seed_rate_configurations():
    """Seed initial rate configurations."""
    from app.database import AsyncSessionLocal
    
    print("Seeding rate configurations...")
    
    default_rates = [
        # Material Costs
        {"key": "material.steel_mild_price_per_kg", "name": "Mild Steel Price per KG", "category": "material", "value": 4.5, "unit": "AED/kg"},
        {"key": "material.steel_ss304_price_per_kg", "name": "SS304 Steel Price per KG", "category": "material", "value": 18.0, "unit": "AED/kg"},
        {"key": "material.steel_ss316_price_per_kg", "name": "SS316 Steel Price per KG", "category": "material", "value": 22.0, "unit": "AED/kg"},
        {"key": "material.wastage_percentage", "name": "Material Wastage", "category": "material", "value": 10.0, "unit": "%"},
        
        # Cutting Costs
        {"key": "cutting.plasma_rate_per_meter", "name": "Plasma Cutting Rate", "category": "cutting", "value": 8.0, "unit": "AED/m"},
        {"key": "cutting.laser_rate_per_meter", "name": "Laser Cutting Rate", "category": "cutting", "value": 12.0, "unit": "AED/m"},
        {"key": "cutting.oxy_fuel_rate_per_meter", "name": "Oxy-Fuel Cutting Rate", "category": "cutting", "value": 5.0, "unit": "AED/m"},
        
        # Welding Costs
        {"key": "welding.mig_rate_per_meter", "name": "MIG Welding Rate", "category": "welding", "value": 15.0, "unit": "AED/m"},
        {"key": "welding.tig_rate_per_meter", "name": "TIG Welding Rate", "category": "welding", "value": 25.0, "unit": "AED/m"},
        {"key": "welding.smaw_rate_per_meter", "name": "SMAW Welding Rate", "category": "welding", "value": 18.0, "unit": "AED/m"},
        
        # Fabrication Costs
        {"key": "fabrication.bending_rate_per_bend", "name": "Bending Rate per Bend", "category": "fabrication", "value": 20.0, "unit": "AED/bend"},
        {"key": "fabrication.rolling_rate_per_meter", "name": "Rolling Rate", "category": "fabrication", "value": 30.0, "unit": "AED/m"},
        {"key": "fabrication.drilling_rate_per_hole", "name": "Drilling Rate per Hole", "category": "fabrication", "value": 5.0, "unit": "AED/hole"},
        
        # Surface Treatment
        {"key": "surface.sandblasting_rate_per_sqm", "name": "Sandblasting Rate", "category": "surface", "value": 15.0, "unit": "AED/m²"},
        {"key": "surface.priming_rate_per_sqm", "name": "Priming Rate", "category": "surface", "value": 12.0, "unit": "AED/m²"},
        {"key": "surface.painting_rate_per_sqm", "name": "Painting Rate", "category": "surface", "value": 18.0, "unit": "AED/m²"},
        {"key": "surface.galvanizing_rate_per_kg", "name": "Galvanizing Rate", "category": "surface", "value": 3.5, "unit": "AED/kg"},
        {"key": "surface.powder_coating_rate_per_sqm", "name": "Powder Coating Rate", "category": "surface", "value": 25.0, "unit": "AED/m²"},
        
        # Labor Costs
        {"key": "labor.welder_hour_rate", "name": "Welder Hourly Rate", "category": "labor", "value": 35.0, "unit": "AED/hour"},
        {"key": "labor.fitter_hour_rate", "name": "Fitter Hourly Rate", "category": "labor", "value": 30.0, "unit": "AED/hour"},
        {"key": "labor.helper_hour_rate", "name": "Helper Hourly Rate", "category": "labor", "value": 20.0, "unit": "AED/hour"},
        
        # Overhead & Margin
        {"key": "overhead.workshop_overhead_percentage", "name": "Workshop Overhead", "category": "overhead", "value": 15.0, "unit": "%"},
        {"key": "overhead.admin_overhead_percentage", "name": "Admin Overhead", "category": "overhead", "value": 10.0, "unit": "%"},
        {"key": "margin.profit_margin_percentage", "name": "Profit Margin", "category": "margin", "value": 20.0, "unit": "%"},
        
        # Consumables
        {"key": "consumables.mig_wire_per_kg", "name": "MIG Wire Cost", "category": "consumables", "value": 12.0, "unit": "AED/kg"},
        {"key": "consumables.co2_gas_per_kg", "name": "CO2 Gas Cost", "category": "consumables", "value": 5.0, "unit": "AED/kg"},
        {"key": "consumables.argon_per_m3", "name": "Argon Gas Cost", "category": "consumables", "value": 8.0, "unit": "AED/m³"},
        {"key": "consumables.grinding_disc_each", "name": "Grinding Disc Cost", "category": "consumables", "value": 3.0, "unit": "AED/piece"},
        {"key": "consumables.cutting_disc_each", "name": "Cutting Disc Cost", "category": "consumables", "value": 2.5, "unit": "AED/piece"},
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if rates already exist
            result = await session.execute(text("SELECT COUNT(*) FROM rate_configurations"))
            count = result.scalar()
            
            if count > 0:
                print(f"⚠ Rate configurations already exist ({count} records). Skipping seed.")
                return
            
            # Insert default rates
            for rate_data in default_rates:
                rate = RateConfiguration(
                    key=rate_data["key"],
                    name=rate_data["name"],
                    category=rate_data["category"],
                    value=rate_data["value"],
                    unit=rate_data.get("unit"),
                    is_active=True
                )
                session.add(rate)
            
            await session.commit()
            print(f"✓ Successfully seeded {len(default_rates)} rate configurations")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ Error seeding rate configurations: {e}")
            raise


async def reset_database():
    """Drop and recreate database with seed data."""
    print("=" * 60)
    print("RESETTING DATABASE")
    print("=" * 60)
    
    await drop_database()
    await create_database()
    await seed_rate_configurations()
    
    print("=" * 60)
    print("✓ Database reset complete")
    print("=" * 60)


async def init_database():
    """Initialize database with tables and seed data."""
    print("=" * 60)
    print("INITIALIZING DATABASE")
    print("=" * 60)
    
    await create_database()
    await seed_rate_configurations()
    
    print("=" * 60)
    print("✓ Database initialization complete")
    print("=" * 60)


async def test_connection():
    """Test database connection."""
    print("Testing database connection...")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        print(f"✓ Database connection successful")
        print(f"  Database URL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    command = sys.argv[1] if len(sys.argv) > 1 else "init"
    
    if command == "init":
        asyncio.run(init_database())
    elif command == "reset":
        asyncio.run(reset_database())
    elif command == "create":
        asyncio.run(create_database())
    elif command == "drop":
        asyncio.run(drop_database())
    elif command == "seed":
        asyncio.run(seed_rate_configurations())
    elif command == "test":
        asyncio.run(test_connection())
    else:
        print("Usage: python init_db.py [init|reset|create|drop|seed|test]")
        print("  init  - Create tables and seed data (default)")
        print("  reset - Drop and recreate tables with seed data")
        print("  create - Create tables only")
        print("  drop - Drop all tables")
        print("  seed - Seed rate configurations")
        print("  test - Test database connection")
