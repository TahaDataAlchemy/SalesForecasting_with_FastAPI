from sqlalchemy import Column, Integer, String, ForeignKey,Float,DateTime
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)   # Usually VARCHAR in Northwind
    company_name = Column(String, nullable=False)
    contact_name = Column(String)
    contact_title = Column(String)
    address = Column(String)
    city = Column(String)
    region = Column(String)
    postal_code = Column(String)
    country = Column(String)
    phone = Column(String)
    fax = Column(String)

    orders = relationship("Order", back_populates="customer")

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"))
    employee_id = Column(Integer)   # Could also link to Employee table
    order_date = Column(DateTime)
    required_date = Column(DateTime)
    shipped_date = Column(DateTime)
    ship_via = Column(Integer)
    freight = Column(Float)
    ship_name = Column(String)
    ship_address = Column(String)
    ship_city = Column(String)
    ship_region = Column(String)
    ship_postal_code = Column(String)
    ship_country = Column(String)

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    order_details = relationship("OrderDetail", back_populates="order")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String, nullable=False)
    supplier_id = Column(Integer)   # Could link to Supplier table
    category_id = Column(Integer)   # Could link to Category table
    quantity_per_unit = Column(String)
    unit_price = Column(Float)
    units_in_stock = Column(Integer)
    units_on_order = Column(Integer)
    reorder_level = Column(Integer)
    discontinued = Column(Integer)

    # Relationships
    order_details = relationship("OrderDetail", back_populates="product")


class OrderDetail(Base):
    __tablename__ = "order_details"

    order_id = Column(Integer, ForeignKey("orders.order_id"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    discount = Column(Float, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="order_details")
    product = relationship("Product", back_populates="order_details")