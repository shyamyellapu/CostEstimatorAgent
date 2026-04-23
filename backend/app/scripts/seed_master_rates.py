"""
Database Seeder for Master Rate Configuration
==============================================

Seeds the database with C&J Gulf Equipment Manufacturing LLC
standard rates from the master rate card.

Usage:
    python -m app.scripts.seed_master_rates
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, Base, AsyncSessionLocal
from app.models import RateConfiguration
from app.services.master_rates import get_all_rates

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def seed_master_rates():
    """Seed master rates into the database."""
    logger.info("Starting master rate seeding...")
    
    async with AsyncSessionLocal() as session:
        # Get all rates from master configuration
        master_rates = get_all_rates()
        
        logger.info(f"Found {len(master_rates)} rates to seed")
        
        for rate_data in master_rates:
            key = rate_data["key"]
            
            # Check if rate already exists
            stmt = select(RateConfiguration).where(RateConfiguration.key == key)
            result = await session.execute(stmt)
            existing_rate = result.scalar_one_or_none()
            
            if existing_rate:
                # Update existing rate
                existing_rate.name = rate_data["name"]
                existing_rate.category = rate_data["category"]
                existing_rate.value = rate_data["value"]
                existing_rate.unit = rate_data["unit"]
                existing_rate.description = rate_data["description"]
                existing_rate.is_active = rate_data["is_active"]
                logger.info(f"  Updated: {key} = {rate_data['value']} {rate_data['unit']}")
            else:
                # Create new rate
                new_rate = RateConfiguration(**rate_data)
                session.add(new_rate)
                logger.info(f"  Created: {key} = {rate_data['value']} {rate_data['unit']}")
        
        await session.commit()
        logger.info("Master rate seeding completed successfully!")


async def verify_rates():
    """Verify that rates were seeded correctly."""
    logger.info("\nVerifying seeded rates...")
    
    async with AsyncSessionLocal() as session:
        stmt = select(RateConfiguration).where(RateConfiguration.is_active == True)
        result = await session.execute(stmt)
        rates = result.scalars().all()
        
        logger.info(f"Found {len(rates)} active rates in database")
        
        # Group by category
        categories = {}
        for rate in rates:
            if rate.category not in categories:
                categories[rate.category] = []
            categories[rate.category].append(rate)
        
        for category, cat_rates in sorted(categories.items()):
            logger.info(f"\n{category.upper()} ({len(cat_rates)} rates):")
            for rate in cat_rates:
                logger.info(f"  - {rate.key}: {rate.value} {rate.unit}")


async def main():
    """Main execution."""
    try:
        # Create tables if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Seed rates
        await seed_master_rates()
        
        # Verify
        await verify_rates()
        
    except Exception as e:
        logger.error(f"Error during seeding: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
