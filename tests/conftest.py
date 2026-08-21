import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.backend.database import Base
from apps.backend.models import Customer, Transaction

@pytest.fixture(scope="function")
def test_db():
    """
    Fixture to create an in-memory SQLite database and teardown after each test.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Pre-populate with standard test customer
    cust = Customer(
        id="cust_test_123",
        tenure_days=100,
        merchant_category="SaaS",
        preferred_payment_method="card",
        historical_success_rate=0.80,
        historical_failure_rate=0.20,
        velocity_24h=0,
        time_since_last_success_days=2.0
    )
    db.add(cust)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
