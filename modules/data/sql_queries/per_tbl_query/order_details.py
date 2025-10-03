class OrderDetailQuery:
    GET_ALL_ORDER_DETAILS = """
        SELECT * FROM order_details;
    """

    GET_ORDER_DETAILS_BY_ORDER = """
        SELECT * FROM order_details WHERE order_id = :order_id;
    """
