# migration_script.py
# This script can be run to fix existing relationships in the database
from sqlalchemy import create_engine, MetaData, Table, select, insert
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Replace with your database URL
DATABASE_URL = "sqlite:///./app.db"  # Update this to your database URL

def run_migration():
    """
    Fix existing relationships in the database by ensuring all association tables
    are properly populated based on the API responses.
    """
    logger.info("Starting database migration to fix relationships")
    
    # Connect to the database
    engine = create_engine(DATABASE_URL)
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get tables
        events_table = metadata.tables['events']
        programs_table = metadata.tables['programs'] 
        departments_table = metadata.tables['departments']
        event_department_assoc = metadata.tables['event_department_association']
        event_program_assoc = metadata.tables['event_program_association']
        program_department_assoc = metadata.tables['program_department_association']
        
        # Fix event relationships
        logger.info("Checking and fixing event relationships")
        events = session.execute(select(events_table)).fetchall()
        for event in events:
            event_id = event.id
            logger.info(f"Processing event ID: {event_id}")
            
            # Debug info: Check what's already in the association tables
            existing_dept_assocs = session.execute(
                select(event_department_assoc).where(event_department_assoc.c.event_id == event_id)
            ).fetchall()
            
            existing_prog_assocs = session.execute(
                select(event_program_assoc).where(event_program_assoc.c.event_id == event_id)
            ).fetchall()
            
            logger.info(f"Existing department associations: {existing_dept_assocs}")
            logger.info(f"Existing program associations: {existing_prog_assocs}")
            
            # Implement your logic to check and fix missing relationships here
            # For example:
            # - Verify which events in your response JSON have relationships
            # - Insert missing associations in the appropriate association tables
            
        # Fix program relationships  
        logger.info("Checking and fixing program relationships")
        programs = session.execute(select(programs_table)).fetchall()
        for program in programs:
            program_id = program.id
            logger.info(f"Processing program ID: {program_id}")
            
            # Debug info: Check what's in the association table
            existing_dept_assocs = session.execute(
                select(program_department_assoc).where(program_department_assoc.c.program_id == program_id)
            ).fetchall()
            
            logger.info(f"Existing department associations: {existing_dept_assocs}")
            
            # Implement your logic here to fix program-department relationships
            
        # Commit the changes
        session.commit()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Migration failed: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()