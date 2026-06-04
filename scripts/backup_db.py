import os
import shutil
import datetime

def backup_databases():
    # Database files to back up
    db_files = ["learnloop.db", "carestance.db", "database.db"]
    
    # Target directory for backups
    backup_dir = "backups"
    
    # Create the backup directory if it doesn't exist
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"Created directory: {backup_dir}")
    
    # Get current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backups_created = []
    
    for db_file in db_files:
        if os.path.exists(db_file):
            # Create timestamped filename
            base, ext = os.path.splitext(db_file)
            backup_filename = f"{base}_{timestamp}{ext}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Copy the file
            shutil.copy2(db_file, backup_path)
            print(f"Successfully backed up {db_file} to {backup_path}")
            backups_created.append(backup_path)
        else:
            print(f"Warning: {db_file} not found, skipping.")
    
    return backups_created

if __name__ == "__main__":
    print("Starting database backup...")
    try:
        created = backup_databases()
        if created:
            print(f"Backup complete. {len(created)} files backed up.")
        else:
            print("No database files found to back up.")
    except Exception as e:
        print(f"Error during backup: {e}")
