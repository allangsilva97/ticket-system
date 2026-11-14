"""
Cria (ou redefine a senha de) um usuário admin.

Uso:
    python create_admin.py                       # usa os valores padrão abaixo
    python create_admin.py email@x.com SenhaForte123 "Nome Completo"
"""
import sys

from database import SessionLocal, init_db
from models import User, UserRole
from auth import get_password_hash

DEFAULT_EMAIL = "admin@ticketsystem.local"
DEFAULT_PASSWORD = "Admin@123"
DEFAULT_NAME = "Administrador"


def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL).strip().lower()
    password = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PASSWORD
    name = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_NAME

    if len(password) < 8:
        sys.exit("A senha precisa ter pelo menos 8 caracteres.")

    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.hashed_password = get_password_hash(password)
            user.role = UserRole.ADMIN
            user.is_active = True
            action = "atualizado"
        else:
            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name=name,
                role=UserRole.ADMIN,
                is_active=True,
                language="pt-BR",
            )
            db.add(user)
            action = "criado"
        db.commit()
        # Never echo the password: terminal output often ends up in logs
        print(f"Admin {action}: {email}")
        if action == "atualizado":
            print("Atenção: a senha deste usuário foi redefinida e o papel definido como admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
