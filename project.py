import pymysql

from supermarket import initialize_database, customer_menu, staff_menu


def display_main_menu():
    print("\nWelcome to the Supermarket Management System")
    print("1. Login as Customer")
    print("2. Login as Staff")
    print("3. Exit")


def main():
    try:
        initialize_database()
    except pymysql.MySQLError as e:
        print(f"Could not connect to the database: {e}")
        print("Check DB_HOST, DB_USER and DB_PASSWORD environment variables.")
        return

    while True:
        display_main_menu()
        choice = input("Enter your choice: ")

        if choice == "1":
            customer_menu()
        elif choice == "2":
            staff_menu()
        elif choice == "3":
            print("Exiting. Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
