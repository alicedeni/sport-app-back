import sys
import os
import csv
import logging
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infra.db.sqlalchemy_db import get_session
from app.domain.models import User

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def import_csv_to_users_table(csv_file):
    """
    Импортирует пользователей из CSV файла
    
    Формат CSV: id, surname, name, midname, email, password, age
    
    Args:
        csv_file: Путь к CSV файлу
    """
    if not os.path.exists(csv_file):
        logger.error(f"CSV file not found: {csv_file}")
        return
    
    try:
        imported_count = 0
        skipped_count = 0
        
        with get_session() as session:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                header = next(reader)
                logger.info(f"CSV columns: {header}")
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        if len(row) < 7:
                            logger.warning(f"Row {row_num}: Not enough columns, skipping")
                            skipped_count += 1
                            continue
                        
                        user_id, surname, name, midname, email, password, age = row[:7]
                        
                        existing_user = session.query(User).filter(
                            (User.id == int(user_id)) | (User.email == email.lower())
                        ).first()
                        
                        if existing_user:
                            logger.warning(f"Row {row_num}: User with ID {user_id} or email {email} already exists, skipping")
                            skipped_count += 1
                            continue
                        
                        new_user = User(
                            id=int(user_id),
                            surname=surname,
                            name=name,
                            midname=midname,
                            email=email.lower(),
                            password=generate_password_hash(password),
                            age=int(age) if age else None,
                            points=0,
                            league='silver'
                        )
                        
                        session.add(new_user)
                        imported_count += 1
                        
                    except Exception as e:
                        logger.error(f"Row {row_num}: Error importing - {e}")
                        skipped_count += 1
                        continue
                
                session.commit()
                
        logger.info(f"Import completed:")
        logger.info(f"  Imported: {imported_count} users")
        logger.info(f"  Skipped: {skipped_count} users")
        
    except Exception as e:
        logger.error(f"Error importing CSV file: {e}", exc_info=True)
        raise


def export_users_to_csv(csv_file):
    """
    Экспортирует пользователей в CSV файл
    
    Args:
        csv_file: Путь к выходному CSV файлу
    """
    try:
        with get_session() as session:
            users = session.query(User).all()
            
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                
                writer.writerow([
                    'id', 'surname', 'name', 'midname', 'email', 
                    'age', 'gender', 'height', 'weight', 'points', 
                    'team_id', 'league', 'role', 'created_at'
                ])
                
                for user in users:
                    writer.writerow([
                        user.id,
                        user.surname,
                        user.name,
                        user.midname,
                        user.email,
                        user.age,
                        user.gender,
                        user.height,
                        user.weight,
                        user.points,
                        user.team_id,
                        user.league,
                        user.role,
                        user.created_at
                    ])
        
        logger.info(f"Exported {len(users)} users to {csv_file}")
        
    except Exception as e:
        logger.error(f"Error exporting users to CSV: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Import/Export users from/to CSV')
    parser.add_argument('--import', dest='import_file', help='Import users from CSV file')
    parser.add_argument('--export', dest='export_file', help='Export users to CSV file')
    
    args = parser.parse_args()
    
    if args.import_file:
        import_csv_to_users_table(args.import_file)
    elif args.export_file:
        export_users_to_csv(args.export_file)
    else:
        print("Usage:")
        print("  python import_db.py --import users.csv")
        print("  python import_db.py --export users_export.csv")
