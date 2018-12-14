import db
import sys

from utils import register_new_user
from models import User, PermissionsLevels

if __name__ == "__main__":
    if sys.argv[1] == "add":

        session = db.Session()
        x = session.query(User).get(int(sys.argv[2]))
        if x is None:
            x = register_new_user(session, int(sys.argv[2]))
        x.permissions = PermissionsLevels.ADMIN
        session.commit()
        session.close()

    elif sys.argv[1] == "del":

        session = db.Session()
        x = session.query(User).get(int(sys.argv[2]))
        if x is not None:
            x.permissions = PermissionsLevels.USER
            session.commit()
        session.close()

    elif sys.argv[1] == "test":

        session = db.Session()
        admins = session.query(User).filter_by(permissions=PermissionsLevels.ADMIN).all()
        for admin in admins:
            admin.cash += 5000 * 100
        session.commit()
        session.close()

    elif sys.argv[1] == "list":

        session = db.Session()
        admins = session.query(User).filter_by(permissions=PermissionsLevels.ADMIN).all()
        for admin in admins:
            print("admin:", admin.id)
        session.close()

    else:
        print("usage: python manage_admins.py (add|del) admin_id")
