from sqlalchemy import func
from sqlalchemy.orm import Session
from modules.ORM.models import Order, OrderDetail, Product, Customer
from modules.ORM.orm import engine
from sqlalchemy.orm import Session
from sqlalchemy import func

session = Session(bind=engine)

class SalesQuery:
    @staticmethod
    def product_wise_monthly_sales(session):
        return (
            session.query(
                Product.product_name,
                func.date_trunc('month', Order.order_date).label("month"),
                func.sum(
                    OrderDetail.unit_price * OrderDetail.quantity * (1 - OrderDetail.discount)
                ).label("total_sales")
            )
            .join(OrderDetail, OrderDetail.product_id == Product.product_id)  
            .join(Order, Order.order_id == OrderDetail.order_id)               
            .group_by(Product.product_name, func.date_trunc('month', Order.order_date))
            .order_by(func.date_trunc('month', Order.order_date), Product.product_name)
        )

    @staticmethod
    def customer_wise_sales(session):
        return (
            session.query(
                Customer.company_name,
                func.date_trunc('month', Order.order_date).label("month"),
                func.sum(
                    OrderDetail.unit_price * OrderDetail.quantity * (1 - OrderDetail.discount)
                ).label("total_sales")
            )
            .join(Order, Order.customer_id == Customer.customer_id)           
            .join(OrderDetail, OrderDetail.order_id == Order.order_id)         
            .group_by(Customer.company_name, func.date_trunc('month', Order.order_date))
            .order_by(func.date_trunc('month', Order.order_date), Customer.company_name)
        )

    @staticmethod
    def customer_product_wise_sales(session):
        return (
            session.query(
                Customer.company_name,
                Product.product_name,
                func.date_trunc('month', Order.order_date).label("month"),
                func.sum(
                    OrderDetail.unit_price * OrderDetail.quantity * (1 - OrderDetail.discount)
                ).label("total_sales")
            )
            .join(Order, Order.customer_id == Customer.customer_id)            
            .join(OrderDetail, OrderDetail.order_id == Order.order_id)         
            .join(Product, Product.product_id == OrderDetail.product_id)       
            .group_by(Customer.company_name, Product.product_name, func.date_trunc('month', Order.order_date))
            .order_by(func.date_trunc('month', Order.order_date), Customer.company_name, Product.product_name)
        )
    
    @staticmethod
    def city_wise_sales(session):
        return (
            session.query(
                Customer.city,
                func.date_trunc('month', Order.order_date).label("month"),
                func.sum(
                    OrderDetail.unit_price * OrderDetail.quantity * (1 - OrderDetail.discount)
                ).label("total_sales")
            )
            .join(Order, Order.customer_id == Customer.customer_id)
            .join(OrderDetail, OrderDetail.order_id == Order.order_id)
            .group_by(Customer.city, func.date_trunc('month', Order.order_date))
            .order_by(func.date_trunc('month', Order.order_date), Customer.city)
        )