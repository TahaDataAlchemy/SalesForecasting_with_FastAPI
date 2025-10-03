class ProductQuery:
    GET_ALL_PRODUCTS = """
        SELECT * FROM products;
    """

    GET_PRODUCT_BY_ID = """
        SELECT * FROM products WHERE product_id = :id;
    """

    GET_PRODUCTS_BY_CATEGORY = """
        SELECT * FROM products WHERE category_id = :category_id;
    """
