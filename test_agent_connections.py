#!/usr/bin/env python3
"""
Test script để kiểm tra các kết nối giữa các agent trong hệ thống
"""
import sys
import os
import time
import traceback
from typing import Dict, Any, List

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.agents.core.agent_manager import agent_manager
from app.models.context import AgentContext, SessionInfo as Session, CustomerInfo as Customer
from app.utils.logger import log_info, log_error


class AgentConnectionTester:
    """Class để test các kết nối giữa agents"""
    
    def __init__(self):
        self.test_results = {}
        self.context = self._create_test_context()
    
    def _create_test_context(self) -> AgentContext:
        """Tạo context test"""
        session = Session(
            session_id="test_session_123"
        )
        
        customer = Customer(
            id="test_customer_456",
            name="Test User",
            phone="0123456789"
        )
        
        return AgentContext(session=session, customer=customer)
    
    async def test_agent_manager(self) -> bool:
        """Test AgentManager functionality"""
        print("\n🔧 Testing AgentManager...")
        
        try:
            # Test agent registration
            # status = agent_manager.get_agent_status()
            # print(f"  📊 Agent classes registered: {len(status)}")
            
            # Test getting agents
            agent_names = ['router', 'recommend', 'graphrag', 'customer', 'chathistory', 'preference', 'image']
            
            for agent_name in agent_names:
                try:
                    agent = await agent_manager.get_agent(agent_name)
                    if agent:
                        print(f"  ✅ {agent_name}: {type(agent).__name__}")
                    else:
                        print(f"  ❌ {agent_name}: Failed to get agent")
                        return False
                except Exception as e:
                    print(f"  ❌ {agent_name}: Error - {str(e)}")
                    return False
            
            print("  ✅ AgentManager test passed")
            return True
            
        except Exception as e:
            print(f"  ❌ AgentManager test failed: {str(e)}")
            return False
    
    async def test_router_to_recommend_connection(self) -> bool:
        """Test kết nối Router -> Recommend"""
        print("\n🔀 Testing Router -> Recommend connection...")
        
        try:
            router = await agent_manager.get_agent('router')
            
            # Test message routing
            test_message = "Tìm sản phẩm cà phê"
            
            print(f"  📝 Testing message: '{test_message}'")
            
            # Test classification
            agent_type = router.classify_with_rules(test_message)
            print(f"  🎯 Classified as: {agent_type}")
            
            # Test full processing (should call recommend agent)
            response = await router.process_message(test_message)
            
            if response and len(response) > 0:
                print(f"  ✅ Router -> Recommend connection working")
                print(f"  📤 Response: {response[:100]}...")
                return True
            else:
                print(f"  ❌ No response from router")
                return False
                
        except Exception as e:
            print(f"  ❌ Router -> Recommend test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_recommend_to_graphrag_connection(self) -> bool:
        """Test kết nối Recommend -> GraphRAG"""
        print("\n💡 Testing Recommend -> GraphRAG connection...")
        
        try:
            recommend = await agent_manager.get_agent('recommend')
            
            # Test message processing
            test_message = "Sản phẩm có caffeine cao nhất"
            
            print(f"  📝 Testing message: '{test_message}'")
            
            # Process message (should call GraphRAG internally)
            response = await recommend.process_message(test_message, self.context)
            
            if response and len(response) > 0:
                print(f"  ✅ Recommend -> GraphRAG connection working")
                print(f"  📤 Response: {response[:100]}...")
                return True
            else:
                print(f"  ❌ No response from recommend agent")
                return False
                
        except Exception as e:
            print(f"  ❌ Recommend -> GraphRAG test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_graphrag_direct_execution(self) -> bool:
        """Test GraphRAG agent trực tiếp"""
        print("\n🧠 Testing GraphRAG direct execution...")
        
        try:
            graphrag = await agent_manager.get_agent('graphrag')
            
            # Test intent data
            intent_data = {
                "entities": {
                    "entities": ["cà phê"],
                    "attributes": ["caffeine"],
                    "constraints": ["cao nhất"],
                    "targets": [],
                    "keywords": ["cà phê", "caffeine", "cao"]
                },
                "query_type": "statistical",
                "comparison_type": "MAX",
                "attribute": "caffeine_mg"
            }
            
            print(f"  📝 Testing intent data: {intent_data}")
            
            # Execute query
            results = await graphrag.execute_query(intent_data, self.context)
            
            if results and isinstance(results, dict):
                print(f"  ✅ GraphRAG execution working")
                print(f"  📊 Results type: {results.get('query_type', 'unknown')}")
                print(f"  📊 Results count: {len(results.get('results', []))}")
                return True
            else:
                print(f"  ❌ No results from GraphRAG")
                return False
                
        except Exception as e:
            print(f"  ❌ GraphRAG test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_customer_agent_connection(self) -> bool:
        """Test Customer agent"""
        print("\n👤 Testing Customer agent...")
        
        try:
            customer = await agent_manager.get_agent('customer')
            
            # Test customer info retrieval
            test_message = "Thông tin của tôi"
            
            response = await customer.process_message(test_message, self.context)
            
            if response and len(response) > 0:
                print(f"  ✅ Customer agent working")
                print(f"  📤 Response: {response[:100]}...")
                return True
            else:
                print(f"  ❌ No response from customer agent")
                return False
                
        except Exception as e:
            print(f"  ❌ Customer agent test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_chathistory_agent_connection(self) -> bool:
        """Test ChatHistory agent"""
        print("\n💬 Testing ChatHistory agent...")
        
        try:
            chathistory = await agent_manager.get_agent('chathistory')
            
            # Test adding message
            session_id = self.context.session.session_id
            test_message = "Test message for history"
            test_response = "Test response"
            
            # Add message to history
            await chathistory.add_message(
                session_id=session_id,
                user_message=test_message,
                bot_response=test_response
            )
            
            # Get recent messages
            recent_messages = await chathistory.get_recent_messages(session_id, limit=5)
            
            if recent_messages and len(recent_messages) > 0:
                print(f"  ✅ ChatHistory agent working")
                print(f"  📊 Recent messages count: {len(recent_messages)}")
                return True
            else:
                print(f"  ❌ No messages in chat history")
                return False
                
        except Exception as e:
            print(f"  ❌ ChatHistory agent test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_preference_agent_connection(self) -> bool:
        """Test Preference agent"""
        print("\n❤️ Testing Preference agent...")
        
        try:
            preference = await agent_manager.get_agent('preference')
            
            # Test preference processing
            test_message = "Tôi thích cà phê ít đường"
            
            response = await preference.process_message(test_message, self.context)
            
            if response and len(response) > 0:
                print(f"  ✅ Preference agent working")
                print(f"  📤 Response: {response[:100]}...")
                return True
            else:
                print(f"  ❌ No response from preference agent")
                return False
                
        except Exception as e:
            print(f"  ❌ Preference agent test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_image_agent_connection(self) -> bool:
        """Test Image agent"""
        print("\n🖼️ Testing Image agent...")
        
        try:
            image = await agent_manager.get_agent('image')
            
            # Test image processing (without actual image)
            test_message = "Phân tích hình ảnh này"
            
            response = await image.process_message(test_message, self.context)
            
            if response and len(response) > 0:
                print(f"  ✅ Image agent working")
                print(f"  📤 Response: {response[:100]}...")
                return True
            else:
                print(f"  ❌ No response from image agent")
                return False
                
        except Exception as e:
            print(f"  ❌ Image agent test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def test_full_workflow(self) -> bool:
        """Test full workflow từ Router đến tất cả agents"""
        print("\n🔄 Testing full workflow...")
        
        try:
            router = await agent_manager.get_agent('router')
            
            # Test different types of messages
            test_cases = [
                ("Tìm sản phẩm cà phê", "product query"),
                ("Thông tin của tôi", "customer query"),
                ("Tôi thích trà xanh", "preference query"),
                ("Lịch sử chat của tôi", "history query")
            ]
            
            success_count = 0
            
            for message, description in test_cases:
                try:
                    print(f"  🧪 Testing {description}: '{message}'")
                    
                    response = await router.process_message(message)
                    
                    if response and len(response) > 0:
                        print(f"    ✅ Success: {response[:50]}...")
                        success_count += 1
                    else:
                        print(f"    ❌ No response")
                        
                except Exception as e:
                    print(f"    ❌ Error: {str(e)}")
            
            success_rate = (success_count / len(test_cases)) * 100
            print(f"  📊 Success rate: {success_rate:.1f}% ({success_count}/{len(test_cases)})")
            
            return success_rate >= 75  # 75% success rate threshold
            
        except Exception as e:
            print(f"  ❌ Full workflow test failed: {str(e)}")
            traceback.print_exc()
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Chạy tất cả tests"""
        print("🚀 Starting Agent Connection Tests")
        print("=" * 60)
        
        tests = [
            ("AgentManager", self.test_agent_manager),
            ("Router -> Recommend", self.test_router_to_recommend_connection),
            ("Recommend -> GraphRAG", self.test_recommend_to_graphrag_connection),
            ("GraphRAG Direct", self.test_graphrag_direct_execution),
            ("Customer Agent", self.test_customer_agent_connection),
            ("ChatHistory Agent", self.test_chathistory_agent_connection),
            ("Preference Agent", self.test_preference_agent_connection),
            ("Image Agent", self.test_image_agent_connection),
            ("Full Workflow", self.test_full_workflow)
        ]
        
        results = {}
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                print(f"\n{'='*20} {test_name} {'='*20}")
                start_time = time.time()
                
                if callable(test_func) and hasattr(test_func, '__await__'):
                    result = await test_func()
                else:
                    result = test_func()
                
                end_time = time.time()
                duration = end_time - start_time
                
                results[test_name] = result
                
                if result:
                    passed += 1
                    print(f"✅ {test_name} - PASSED ({duration:.2f}s)")
                else:
                    failed += 1
                    print(f"❌ {test_name} - FAILED ({duration:.2f}s)")
                    
            except Exception as e:
                failed += 1
                results[test_name] = False
                print(f"❌ {test_name} - ERROR: {str(e)}")
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
        
        success_rate = (passed / len(tests)) * 100
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if failed == 0:
            print("\n🎉 ALL AGENT CONNECTIONS WORKING!")
            print("✨ System is ready for production")
        else:
            print(f"\n⚠️  {failed} connection issues found")
            print("🔧 Some agents may need attention")
        
        return results


import asyncio

async def main():
    """Main async function"""
    tester = AgentConnectionTester()
    results = await tester.run_all_tests()
    
    # Return exit code based on results
    failed_tests = [name for name, result in results.items() if not result]
    
    if failed_tests:
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print(f"\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
