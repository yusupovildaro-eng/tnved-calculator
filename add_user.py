#!/usr/bin/env python3
"""
Управление пользователями ТН ВЭД калькулятора.

  python3 add_user.py <логин> <пароль>   — добавить/обновить
  python3 add_user.py <логин>             — спросит пароль
  python3 add_user.py --list              — список пользователей
  python3 add_user.py --delete <логин>    — удалить пользователя
"""
import sys, json, os, hashlib, getpass

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

def hash_password(password):
    salt = os.urandom(16)
    key  = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"pbkdf2:{salt.hex()}:{key.hex()}"

def load():
    try:
        with open(USERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    print(f"Сохранено в {USERS_FILE}")

def main():
    args = sys.argv[1:]

    if not args or args[0] == '--list':
        users = load()
        if not users:
            print("Пользователей нет.")
        else:
            print(f"Пользователи ({len(users)}):")
            for u in users:
                print(f"  • {u}")
        return

    if args[0] == '--delete':
        if len(args) < 2:
            print("Укажите логин: python3 add_user.py --delete <логин>")
            sys.exit(1)
        users = load()
        login = args[1]
        if login in users:
            del users[login]
            save(users)
            print(f"Пользователь '{login}' удалён.")
        else:
            print(f"Пользователь '{login}' не найден.")
        return

    login = args[0]
    if len(args) >= 2:
        password = args[1]
    else:
        password = getpass.getpass(f"Пароль для '{login}': ")
        confirm  = getpass.getpass("Повторите пароль: ")
        if password != confirm:
            print("Пароли не совпадают.")
            sys.exit(1)

    users  = load()
    action = 'обновлён' if login in users else 'добавлен'
    users[login] = hash_password(password)
    save(users)
    print(f"Пользователь '{login}' {action}.")

if __name__ == '__main__':
    main()
