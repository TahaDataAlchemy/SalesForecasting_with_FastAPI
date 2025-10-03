class CustomerQuery:
    GET_ALL_CUSTOMERS = """
        SELECT * FROM customers;
    """

    GET_CUSTOMER_BY_ID = """
        SELECT * FROM customers WHERE customer_id = :id;
    """
