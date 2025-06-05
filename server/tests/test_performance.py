#!/usr/bin/env python3
"""
Performance Testing Suite - Task 5.11
Add performance testing for database queries and API responses

This test suite performs comprehensive performance testing including:
- Database query performance and optimization validation
- API response time benchmarking
- Load testing for authentication endpoints
- Concurrent user simulation
- Memory usage and resource consumption testing
- Database connection pool performance
"""

import pytest
import os
import sys
import time
import asyncio
import threading
import psutil
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlmodel import Session, select, create_engine, SQLModel, text
from sqlmodel.pool import StaticPool
import requests

# Add server directory to path for imports
server_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, server_dir)

from models import User, UserSession, PasswordResetToken, PlayerCharacter
from auth import get_password_hash

# Import the test app from the API endpoint tests
sys.path.append(os.path.dirname(__file__))
from test_api_auth_endpoints import test_app, client, test_engine, get_test_session

# Performance benchmarks and thresholds
PERFORMANCE_THRESHOLDS = {
    "login_response_time_ms": 500,  # Max 500ms for login
    "registration_response_time_ms": 1000,  # Max 1s for registration
    "profile_response_time_ms": 200,  # Max 200ms for profile access
    "database_query_time_ms": 100,  # Max 100ms for simple queries
    "concurrent_users": 50,  # Should handle 50 concurrent users
    "memory_usage_mb": 500,  # Max 500MB memory usage during tests
    "connection_pool_efficiency": 0.95  # 95% efficiency threshold
}

@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test"""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture
def performance_user_data():
    """Sample user data for performance testing"""
    return {
        "username": "perfuser",
        "email": "perf@example.com",
        "password": "SecurePhrase123!"
    }

@pytest.fixture
def multiple_test_users(test_db):
    """Create multiple users for load testing"""
    users = []
    for i in range(20):
        user_data = {
            "username": f"user_{i}",
            "email": f"user_{i}@example.com",
            "password": "SecurePhrase123!"
        }
        response = client.post("/users/", json=user_data)
        if response.status_code == 200:
            users.append(user_data)
    return users

class PerformanceTimer:
    """Context manager for measuring execution time"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000

class MemoryProfiler:
    """Memory usage profiler for performance testing"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.initial_memory = None
        self.peak_memory = None
        self.final_memory = None
    
    def start(self):
        """Start memory profiling"""
        self.initial_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory = self.initial_memory
    
    def update_peak(self):
        """Update peak memory usage"""
        current_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory
    
    def finish(self):
        """Finish memory profiling"""
        self.final_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
        return {
            "initial_mb": self.initial_memory,
            "peak_mb": self.peak_memory,
            "final_mb": self.final_memory,
            "increase_mb": self.final_memory - self.initial_memory
        }


class TestDatabaseQueryPerformance:
    """Performance tests for database queries"""
    
    def test_user_lookup_query_performance(self, test_db, performance_user_data):
        """Test performance of user lookup queries"""
        # Create test user
        client.post("/users/", json=performance_user_data)
        
        # Test single user lookup by username
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                user = session.exec(
                    select(User).where(User.username == performance_user_data["username"])
                ).first()
        
        assert user is not None
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["database_query_time_ms"]
        print(f"User lookup by username: {timer.duration_ms:.2f}ms")
        
        # Test user lookup by email
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                user = session.exec(
                    select(User).where(User.email == performance_user_data["email"])
                ).first()
        
        assert user is not None
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["database_query_time_ms"]
        print(f"User lookup by email: {timer.duration_ms:.2f}ms")
    
    def test_user_session_query_performance(self, test_db, performance_user_data):
        """Test performance of user session queries"""
        # Create user and login to create session
        client.post("/users/", json=performance_user_data)
        login_response = client.post("/token", data={
            "username": performance_user_data["username"],
            "password": performance_user_data["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Test session lookup performance
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                user_session = session.exec(
                    select(UserSession).where(UserSession.refresh_token == refresh_token)
                ).first()
        
        assert user_session is not None
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["database_query_time_ms"]
        print(f"Session lookup: {timer.duration_ms:.2f}ms")
    
    def test_bulk_user_query_performance(self, test_db, multiple_test_users):
        """Test performance of bulk user queries"""
        # Test bulk user retrieval
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                users = session.exec(select(User)).all()
        
        assert len(users) >= len(multiple_test_users)
        # Allow more time for bulk operations
        assert timer.duration_ms < (PERFORMANCE_THRESHOLDS["database_query_time_ms"] * 5)
        print(f"Bulk user query ({len(users)} users): {timer.duration_ms:.2f}ms")
    
    def test_complex_join_query_performance(self, test_db, performance_user_data):
        """Test performance of complex queries with joins"""
        # Create user and sessions
        client.post("/users/", json=performance_user_data)
        
        # Create multiple sessions for the user
        for _ in range(3):
            client.post("/token", data={
                "username": performance_user_data["username"],
                "password": performance_user_data["password"]
            })
        
        # Test complex query with join
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                result = session.exec(
                    select(User, UserSession)
                    .join(UserSession, User.id == UserSession.user_id)
                    .where(User.username == performance_user_data["username"])
                ).all()
        
        assert len(result) >= 3
        # Allow more time for join operations
        assert timer.duration_ms < (PERFORMANCE_THRESHOLDS["database_query_time_ms"] * 2)
        print(f"Complex join query: {timer.duration_ms:.2f}ms")
    
    def test_database_connection_pool_performance(self, test_db):
        """Test database connection pool efficiency"""
        connection_times = []
        
        # Test multiple rapid connections
        for i in range(20):
            with PerformanceTimer() as timer:
                with Session(test_engine) as session:
                    # Simple query to test connection
                    result = session.exec(text("SELECT 1")).first()
                    assert result == (1,)
            
            connection_times.append(timer.duration_ms)
        
        avg_connection_time = statistics.mean(connection_times)
        max_connection_time = max(connection_times)
        
        # Connection pool should keep times consistent and low
        assert avg_connection_time < 50  # Average under 50ms
        assert max_connection_time < 100  # Max under 100ms
        
        # Check efficiency (std dev should be low indicating consistent performance)
        std_dev = statistics.stdev(connection_times)
        efficiency = 1 - (std_dev / avg_connection_time)
        
        assert efficiency > PERFORMANCE_THRESHOLDS["connection_pool_efficiency"]
        print(f"Connection pool - Avg: {avg_connection_time:.2f}ms, Max: {max_connection_time:.2f}ms, Efficiency: {efficiency:.2%}")


class TestAPIResponsePerformance:
    """Performance tests for API response times"""
    
    def test_registration_endpoint_performance(self, test_db):
        """Test registration endpoint response time"""
        user_data = {
            "username": "speedtest",
            "email": "speedtest@example.com",
            "password": "SecurePhrase123!"
        }
        
        with PerformanceTimer() as timer:
            response = client.post("/users/", json=user_data)
        
        assert response.status_code == 200
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["registration_response_time_ms"]
        print(f"Registration endpoint: {timer.duration_ms:.2f}ms")
    
    def test_login_endpoint_performance(self, test_db, performance_user_data):
        """Test login endpoint response time"""
        # Create user first
        client.post("/users/", json=performance_user_data)
        
        with PerformanceTimer() as timer:
            response = client.post("/token", data={
                "username": performance_user_data["username"],
                "password": performance_user_data["password"]
            })
        
        assert response.status_code == 200
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["login_response_time_ms"]
        print(f"Login endpoint: {timer.duration_ms:.2f}ms")
    
    def test_profile_endpoint_performance(self, test_db, performance_user_data):
        """Test profile endpoint response time"""
        # Create user and login
        client.post("/users/", json=performance_user_data)
        login_response = client.post("/token", data={
            "username": performance_user_data["username"],
            "password": performance_user_data["password"]
        })
        
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        with PerformanceTimer() as timer:
            response = client.get("/users/profile", headers=headers)
        
        assert response.status_code == 200
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["profile_response_time_ms"]
        print(f"Profile endpoint: {timer.duration_ms:.2f}ms")
    
    def test_token_refresh_performance(self, test_db, performance_user_data):
        """Test token refresh endpoint performance"""
        # Create user and login
        client.post("/users/", json=performance_user_data)
        login_response = client.post("/token", data={
            "username": performance_user_data["username"],
            "password": performance_user_data["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        with PerformanceTimer() as timer:
            response = client.post("/auth/refresh", json={
                "refresh_token": refresh_token
            })
        
        assert response.status_code == 200
        assert timer.duration_ms < PERFORMANCE_THRESHOLDS["login_response_time_ms"]
        print(f"Token refresh endpoint: {timer.duration_ms:.2f}ms")
    
    def test_password_reset_request_performance(self, test_db, performance_user_data):
        """Test password reset request performance"""
        # Create user first
        client.post("/users/", json=performance_user_data)
        
        with PerformanceTimer() as timer:
            response = client.post("/auth/forgot-password", json={
                "email": performance_user_data["email"]
            })
        
        assert response.status_code == 200
        # Password reset can be slower due to token generation
        assert timer.duration_ms < (PERFORMANCE_THRESHOLDS["registration_response_time_ms"] * 2)
        print(f"Password reset request: {timer.duration_ms:.2f}ms")


class TestLoadAndConcurrency:
    """Load testing and concurrent user simulation"""
    
    def test_concurrent_login_performance(self, test_db, multiple_test_users):
        """Test concurrent login requests"""
        def login_user(user_data):
            """Helper function to login a single user"""
            with PerformanceTimer() as timer:
                response = client.post("/token", data={
                    "username": user_data["username"],
                    "password": user_data["password"]
                })
                return {
                    "status_code": response.status_code,
                    "duration_ms": timer.duration_ms,
                    "user": user_data["username"]
                }
        
        # Use ThreadPoolExecutor for concurrent requests
        max_workers = min(10, len(multiple_test_users))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            with PerformanceTimer() as total_timer:
                futures = [
                    executor.submit(login_user, user_data) 
                    for user_data in multiple_test_users[:max_workers]
                ]
                
                results = [future.result() for future in as_completed(futures)]
        
        # Verify all logins succeeded
        successful_logins = [r for r in results if r["status_code"] == 200]
        assert len(successful_logins) == max_workers
        
        # Check performance metrics
        response_times = [r["duration_ms"] for r in results]
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        # Concurrent operations may be slower but should still be reasonable
        assert avg_response_time < (PERFORMANCE_THRESHOLDS["login_response_time_ms"] * 2)
        assert max_response_time < (PERFORMANCE_THRESHOLDS["login_response_time_ms"] * 3)
        
        print(f"Concurrent logins ({max_workers} users): Total {total_timer.duration_ms:.2f}ms, "
              f"Avg {avg_response_time:.2f}ms, Max {max_response_time:.2f}ms")
    
    def test_concurrent_profile_access(self, test_db, multiple_test_users):
        """Test concurrent profile access requests"""
        # First, login all users to get tokens
        tokens = []
        for user_data in multiple_test_users[:10]:
            login_response = client.post("/token", data={
                "username": user_data["username"],
                "password": user_data["password"]
            })
            if login_response.status_code == 200:
                tokens.append(login_response.json()["access_token"])
        
        def access_profile(token):
            """Helper function to access profile"""
            headers = {"Authorization": f"Bearer {token}"}
            with PerformanceTimer() as timer:
                response = client.get("/users/profile", headers=headers)
                return {
                    "status_code": response.status_code,
                    "duration_ms": timer.duration_ms
                }
        
        # Concurrent profile access
        with ThreadPoolExecutor(max_workers=10) as executor:
            with PerformanceTimer() as total_timer:
                futures = [executor.submit(access_profile, token) for token in tokens]
                results = [future.result() for future in as_completed(futures)]
        
        # Verify all profile accesses succeeded
        successful_accesses = [r for r in results if r["status_code"] == 200]
        assert len(successful_accesses) == len(tokens)
        
        # Check performance metrics
        response_times = [r["duration_ms"] for r in results]
        avg_response_time = statistics.mean(response_times)
        
        assert avg_response_time < (PERFORMANCE_THRESHOLDS["profile_response_time_ms"] * 2)
        
        print(f"Concurrent profile access ({len(tokens)} users): "
              f"Avg {avg_response_time:.2f}ms")
    
    def test_rapid_sequential_requests(self, test_db, performance_user_data):
        """Test rapid sequential requests from single user"""
        # Create and login user
        client.post("/users/", json=performance_user_data)
        login_response = client.post("/token", data={
            "username": performance_user_data["username"],
            "password": performance_user_data["password"]
        })
        
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Make rapid sequential requests
        response_times = []
        
        for i in range(20):
            with PerformanceTimer() as timer:
                response = client.get("/users/profile", headers=headers)
            
            assert response.status_code == 200
            response_times.append(timer.duration_ms)
        
        # Performance should remain consistent
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
        
        assert avg_response_time < PERFORMANCE_THRESHOLDS["profile_response_time_ms"]
        assert std_dev < (avg_response_time * 0.5)  # Low variance
        
        print(f"Rapid sequential requests: Avg {avg_response_time:.2f}ms, "
              f"Max {max_response_time:.2f}ms, StdDev {std_dev:.2f}ms")


class TestMemoryAndResourceUsage:
    """Memory usage and resource consumption testing"""
    
    def test_memory_usage_during_load(self, test_db, multiple_test_users):
        """Test memory usage during load testing"""
        profiler = MemoryProfiler()
        profiler.start()
        
        # Perform multiple operations that could consume memory
        tokens = []
        
        # Phase 1: Multiple logins
        for user_data in multiple_test_users:
            profiler.update_peak()
            login_response = client.post("/token", data={
                "username": user_data["username"],
                "password": user_data["password"]
            })
            if login_response.status_code == 200:
                tokens.append(login_response.json()["access_token"])
        
        # Phase 2: Multiple profile accesses
        for token in tokens:
            profiler.update_peak()
            headers = {"Authorization": f"Bearer {token}"}
            client.get("/users/profile", headers=headers)
        
        # Phase 3: Token refreshes
        for user_data in multiple_test_users[:5]:
            profiler.update_peak()
            login_response = client.post("/token", data={
                "username": user_data["username"],
                "password": user_data["password"]
            })
            if login_response.status_code == 200:
                refresh_token = login_response.json()["refresh_token"]
                client.post("/auth/refresh", json={"refresh_token": refresh_token})
        
        memory_stats = profiler.finish()
        
        # Memory usage should be reasonable
        assert memory_stats["peak_mb"] < PERFORMANCE_THRESHOLDS["memory_usage_mb"]
        assert memory_stats["increase_mb"] < 100  # Should not increase by more than 100MB
        
        print(f"Memory usage - Initial: {memory_stats['initial_mb']:.2f}MB, "
              f"Peak: {memory_stats['peak_mb']:.2f}MB, "
              f"Increase: {memory_stats['increase_mb']:.2f}MB")
    
    def test_database_connection_cleanup(self, test_db):
        """Test that database connections are properly cleaned up"""
        initial_connections = 0
        
        # Create many sessions to test connection management
        sessions = []
        for i in range(10):
            session = Session(test_engine)
            sessions.append(session)
            # Perform a simple query
            session.exec(text("SELECT 1")).first()
        
        # Close all sessions
        for session in sessions:
            session.close()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Wait a moment for cleanup
        time.sleep(0.1)
        
        # Test that new connections still work efficiently
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                result = session.exec(text("SELECT 1")).first()
                assert result == (1,)
        
        # Connection should be fast if cleanup worked properly
        assert timer.duration_ms < 50
        
        print(f"Post-cleanup connection time: {timer.duration_ms:.2f}ms")


class TestPerformanceRegression:
    """Performance regression testing"""
    
    def test_baseline_performance_metrics(self, test_db, performance_user_data):
        """Establish baseline performance metrics for regression testing"""
        metrics = {}
        
        # Registration performance
        user_data = performance_user_data.copy()
        user_data["username"] = "baseline_user"
        user_data["email"] = "baseline@example.com"
        
        with PerformanceTimer() as timer:
            response = client.post("/users/", json=user_data)
        metrics["registration_ms"] = timer.duration_ms
        assert response.status_code == 200
        
        # Login performance
        with PerformanceTimer() as timer:
            login_response = client.post("/token", data={
                "username": user_data["username"],
                "password": user_data["password"]
            })
        metrics["login_ms"] = timer.duration_ms
        assert login_response.status_code == 200
        
        # Profile access performance
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        
        with PerformanceTimer() as timer:
            response = client.get("/users/profile", headers=headers)
        metrics["profile_access_ms"] = timer.duration_ms
        assert response.status_code == 200
        
        # Database query performance
        with PerformanceTimer() as timer:
            with Session(test_engine) as session:
                user = session.exec(
                    select(User).where(User.username == user_data["username"])
                ).first()
        metrics["db_query_ms"] = timer.duration_ms
        assert user is not None
        
        # Log baseline metrics for future comparison
        print("Baseline Performance Metrics:")
        for metric, value in metrics.items():
            print(f"  {metric}: {value:.2f}ms")
        
        # All metrics should be within thresholds
        assert metrics["registration_ms"] < PERFORMANCE_THRESHOLDS["registration_response_time_ms"]
        assert metrics["login_ms"] < PERFORMANCE_THRESHOLDS["login_response_time_ms"]
        assert metrics["profile_access_ms"] < PERFORMANCE_THRESHOLDS["profile_response_time_ms"]
        assert metrics["db_query_ms"] < PERFORMANCE_THRESHOLDS["database_query_time_ms"]
        
        return metrics


class TestPerformanceUnderStress:
    """Performance testing under stress conditions"""
    
    def test_performance_with_many_sessions(self, test_db, performance_user_data):
        """Test performance when user has many active sessions"""
        # Create user
        client.post("/users/", json=performance_user_data)
        
        # Create many sessions for the same user
        refresh_tokens = []
        for i in range(10):
            login_response = client.post("/token", data={
                "username": performance_user_data["username"],
                "password": performance_user_data["password"]
            })
            if login_response.status_code == 200:
                refresh_tokens.append(login_response.json()["refresh_token"])
        
        # Test login performance with many existing sessions
        with PerformanceTimer() as timer:
            login_response = client.post("/token", data={
                "username": performance_user_data["username"],
                "password": performance_user_data["password"]
            })
        
        assert login_response.status_code == 200
        # Performance should not degrade significantly with many sessions
        assert timer.duration_ms < (PERFORMANCE_THRESHOLDS["login_response_time_ms"] * 1.5)
        
        print(f"Login with {len(refresh_tokens)} existing sessions: {timer.duration_ms:.2f}ms")
    
    def test_performance_with_expired_sessions(self, test_db, performance_user_data):
        """Test performance when there are many expired sessions"""
        # Create user
        client.post("/users/", json=performance_user_data)
        
        # Create sessions and manually expire them
        with Session(test_engine) as session:
            user = session.exec(
                select(User).where(User.username == performance_user_data["username"])
            ).first()
            
            # Create expired sessions directly in database
            for i in range(15):
                expired_session = UserSession(
                    user_id=user.id,
                    refresh_token=f"expired_token_{i}",
                    expires_at=datetime.utcnow() - timedelta(hours=1),
                    is_active=True
                )
                session.add(expired_session)
            session.commit()
        
        # Test login performance with many expired sessions
        with PerformanceTimer() as timer:
            login_response = client.post("/token", data={
                "username": performance_user_data["username"],
                "password": performance_user_data["password"]
            })
        
        assert login_response.status_code == 200
        # Should handle expired sessions efficiently
        assert timer.duration_ms < (PERFORMANCE_THRESHOLDS["login_response_time_ms"] * 2)
        
        print(f"Login with expired sessions cleanup: {timer.duration_ms:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 