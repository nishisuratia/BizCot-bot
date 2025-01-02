# IMPORTANT: All SQL-related logic must be confined to this file.
# Students will not receive credit for this project if SQL code or database logic is found outside of database.py.
# Usage example for interfacing with the database:
#    from database import *
#    data_from_select = Database.select(query, (value_1, value_2, ..., value_n))

import os
import pymysql.cursors

# Environment variables for database connectivity. These should be set securely in your project's environment settings.
db_host = os.environ["DB_HOST"]
db_username = os.environ["DB_USER"]
db_password = os.environ["DB_PASSWORD"]
db_name = os.environ["DB_NAME"]


class Database:
    """
    Provides static methods to handle common database operations.
    """
    @staticmethod
    def connect(close_connection=False):
        try:
            conn = pymysql.connect(host=db_host, port=3306, user=db_username, password=db_password,
                                   db=db_name, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
            print(f"Connected to database {db_name}")
            return conn if not close_connection else True
        except ConnectionError as err:
            print(f"Failed to connect to the database: {err}")
            if close_connection:
                conn.close()
            raise

    def get_response(self, query, values=None, fetch=False, many_entities=False, type=None):
        db_instance = Database()
        connection = db_instance.connect()

        connection = Database.connect()
        cursor = connection.cursor()
        try:
            if values:
                if type == "Proc":
                    cursor.callproc(query, values)
                cursor.executemany(query, values) if many_entities else cursor.execute(query, values)
            else:
                cursor.execute(query)
            if fetch:
                return cursor.fetchall()
        finally:
            connection.commit()
            cursor.close()
            connection.close()

    @staticmethod
    def select(query, values=None, fetch=True):
        return Database().get_response(query, values=values, fetch=fetch)

    @staticmethod
    def insert(query, values=None, many_entities=False):
        return Database().get_response(query, values=values, many_entities=many_entities)

    @staticmethod
    def update(query, values=None):
        return Database().get_response(query, values=values)

    @staticmethod
    def delete(query, values=None):
        return Database().get_response(query, values=values)

    @staticmethod
    def callprocedure(procedure_name, parameters, fetch=False):
        # Assuming you're using pymysql or similar to execute stored procedures
        connection = Database.connect()
        with connection.cursor() as cursor:
            cursor.callproc(procedure_name, parameters)
            if fetch:
                result = cursor.fetchall()
                return result
            connection.commit()

    
    

    @staticmethod
    def get_loyalty_points(customer_id):
        return Database.select("SELECT * FROM Registeredcustomer")
        
    @staticmethod
    def get_employee_performance():
        return Database.select("SELECT * FROM EmployeePerformance")

    @staticmethod
    def get_top_menu_items():
        return Database.callprocedure("PredictTopMenuItems", (), fetch=True)

    @staticmethod
    def get_notifications():
        return Database.select("SELECT * FROM Notifications")

    @staticmethod
    def get_customer_promotions(customer_id):
        return Database.select(
            "SELECT Promotiontype, startdate_promo, enddate_promo FROM Promotion WHERE idPromotion = %s",
            (customer_id,)
        )



class Query:
    """
    The implementation of triggers, functions, and procedures related to the project can be executed directly 
    from MySQL Workbench connected to your RDS instance, as they do not require user parameters and are activated 
    by predefined queries. All calls to these components should be handled through this class.
    """
    # Business Requirement #1: Loyalty Points Query
    CHECK_LOYALTY_POINTS = """
        
    """

    UPDATE_LOYALTY_POINTS_TRIGGER = """

        CREATE PROCEDURE CheckLoyaltyPoints(IN customer_id INT)
        BEGIN
            SELECT loyaltypoints 
            FROM Registeredcustomer
            WHERE Registeredcustomer_id = %s;
        END
        
        CREATE TRIGGER UpdateLoyaltyPoints
        AFTER UPDATE ON `Order`
        FOR EACH ROW
        BEGIN
            IF NEW.status = 'Completed' AND OLD.status <> 'Completed' THEN
                UPDATE Registeredcustomer rc
                JOIN `Order` o ON o.registeredcustomerid_fk = rc.Registeredcustomer_id
                SET rc.loyaltypoints = COALESCE(rc.loyaltypoints, 0) + FLOOR(o.totalamount / 10)
                WHERE o.order_id = NEW.idOrder;
            END IF;
        END
    """

    # Business Requirement #2: Inventory Auto-Restock Notification System Query
    LOW_STOCK_ALERT_TRIGGER = """
        CREATE TRIGGER LowStockAlert
        AFTER UPDATE ON Inventory
        FOR EACH ROW
        BEGIN
            IF NEW.quantity < (SELECT minstocklevel FROM Ingredient WHERE idIngredient = NEW.ingredientid_fk) THEN
                INSERT INTO Notifications (message)
                VALUES (CONCAT('Low stock alert: ', (SELECT ingredientname FROM Ingredient WHERE idIngredient = NEW.ingredientid_fk), ' is running low.'));
            END IF;
        END
    """

    # Business Requirement #3: Employee Performance and Incentive System Query
    EMPLOYEE_PERFORMANCE_VIEW = """
        CREATE VIEW EmployeePerformance AS
        SELECT 
            idWaiter AS EmployeeID,
            'Waiter' AS Role,
            COUNT(DISTINCT assignedtables) * 5 + AVG(ratings) * 10 AS PerformanceScore
        FROM Waiter
        LEFT JOIN Feedback ON Waiter.idWaiter = Feedback.customerfeedback_id
        GROUP BY idWaiter
        UNION ALL
        SELECT 
            idKitchenstaff AS EmployeeID,
            'Kitchen Staff' AS Role,
            COUNT(DISTINCT assignedorderskitchen) * 10 + AVG(ratings) * 5 AS PerformanceScore
        FROM Kitchenstaff
        LEFT JOIN Feedback ON Kitchenstaff.idKitchenstaff = Feedback.customerfeedback_id
        GROUP BY idKitchenstaff;
    """

    CALCULATE_INCENTIVES_PROC = """
        CREATE PROCEDURE CalculateIncentives()
        BEGIN
            INSERT INTO Incentives (EmployeeID, Month, IncentiveAmount)
            SELECT EmployeeID, MONTH(NOW()), PerformanceScore * 10
            FROM EmployeePerformance;
        END
    """

    # Business Requirement #4: No-Show Fee for Reservation Query
    APPLY_NO_SHOW_FEE_TRIGGER = """
        CREATE TRIGGER ApplyNoShowFee
        AFTER UPDATE ON Reservation
        FOR EACH ROW
        BEGIN
            IF NEW.reservationstatus = 'Cancelled' THEN
                INSERT INTO Payment (orderid_fk, paymentmethod, paymentamount, invoice, paymenthistory)
                VALUES (
                    NULL,
                    'Credit Card',
                    20.00,
                    CONCAT('NSF', NEW.idReservation),
                    'Paid'
                );
            END IF;
        END
    """

    # Business Requirement #5: Personalized Promotion Assignment Query
    ASSIGN_CUSTOMER_PROMOTION_TRIGGER = """
        CREATE TRIGGER AssignCustomerPromotion
        AFTER INSERT ON `Order`
        FOR EACH ROW
        BEGIN
            DECLARE customer_category VARCHAR(255);

            SELECT preference_value INTO customer_category
            FROM CustomerPreferences
            WHERE customer_id = NEW.registeredcustomerid_fk AND preference_type = 'Food Category';

            IF customer_category = 'Vegetarian' THEN
                INSERT INTO Promotion (Promotiontype, startdate_promo, enddate_promo)
                VALUES ('Vegetarian Special', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 1 MONTH));
            ELSEIF customer_category = 'Non-Vegetarian' THEN
                INSERT INTO Promotion (Promotiontype, startdate_promo, enddate_promo)
                VALUES ('Meat Lovers Discount', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 1 MONTH));
            END IF;
        END
    """

    # TODO: Create all your queries or calls to your sql stored components here
    pass

class Tables:
    # TODO: Create here all the constants for your table descriptors
    pass