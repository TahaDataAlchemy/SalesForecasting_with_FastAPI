class OrderQuery:
    GET_ALL_ORDERS = """
        SELECT * FROM orders;
    """

    GET_ORDER_BY_ID = """
        SELECT * FROM orders WHERE order_id = :id;
    """

    GET_ORDERS_BY_CUSTOMER = """
        SELECT * FROM orders WHERE customer_id = :customer_id;
    """
