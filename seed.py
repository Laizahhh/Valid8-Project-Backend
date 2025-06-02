# seed.py (in your project root)
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.seeder import run_seeder

if __name__ == "__main__":
    try:
        run_seeder()
    except KeyboardInterrupt:
        print("\n❌ Seeding cancelled by user")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        sys.exit(1)