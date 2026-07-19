import os
from app import app, db, Usuario
from dotenv import load_dotenv

load_dotenv()

def migrar_usuarios():
    with app.app_context():
        # Create the tables if they don't exist
        db.create_all()
        print("Tablas actualizadas (usuarios).")

        # Create default admin user if no users exist
        if Usuario.query.count() == 0:
            chat_id = os.getenv('TELEGRAM_CHAT_ID')
            admin = Usuario(
                username='admin',
                is_admin=True,
                telegram_chat_id=chat_id if chat_id else None
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("Usuario 'admin' creado con contraseña 'admin'.")
            if chat_id:
                print(f"Chat ID {chat_id} asociado al admin.")

if __name__ == "__main__":
    migrar_usuarios()
