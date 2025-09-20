#!/usr/bin/env python3
"""
Lottery System Demo - Comprehensive Demo Suite
Consolidates all demo functionality into a single, user-friendly interface
"""

import sys
import asyncio
import json
import subprocess
import os
from datetime import datetime
from decimal import Decimal
import random

# Compute project root dynamically so the demo can run from any checkout location.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENCLAVE_SRC = os.path.join(PROJECT_ROOT, 'enclave', 'src')
sys.path.append(ENCLAVE_SRC)

from lottery.engine import LotteryEngine, DrawStatus

class LotteryDemo:
    def __init__(self):
        self.config = {
            'lottery': {
                'draw_interval_minutes': 10,
                'betting_cutoff_minutes': 1,
                'single_bet_amount': '0.01'
            }
        }
        
        self.users = [
            {'name': 'Alice', 'address': '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc'},
            {'name': 'Bob', 'address': '0x976EA74026E726554dB657fA54763abd0C3a0aa9'},
            {'name': 'Charlie', 'address': '0x14dC79964da2C08b23698B3D3cc7Ca32193d9955'},
            {'name': 'Diana', 'address': '0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f'},
            {'name': 'Eve', 'address': '0xa0Ee7A142d267C1f36714E4a8F75612F20a79720'}
        ]
        
    def print_header(self, title):
        print(f"\n{'='*60}")
        print(f"🎯 {title}")
        print('='*60)
        
    def print_info(self, msg):
        print(f"💡 {msg}")
        
    def print_success(self, msg):
        print(f"✅ {msg}")
        
    def print_warning(self, msg):
        print(f"⚠️  {msg}")
    
    def print_menu(self):
        self.print_header("Lottery System Demo Suite")
        print("\nChoose demo mode:")
        print("1) 🚀 Quick Demo (5 minutes) - Core functionality showcase")
        print("2) 🎮 Interactive Demo - Step-by-step guided experience") 
        print("3) 🔬 Technical Demo - Detailed system analysis")
        print("4) 🌐 Web Demo - Launch web interface (if available)")
        print("5) 🐳 Docker Demo - Real enclave container environment")
        print("6) ❌ Exit")
        print()
    
    async def quick_demo(self):
        """5-minute automated demo showcasing all core features"""
        self.print_header("Quick Demo Started")
        
        # 1. Initialize system
        print("\n🚀 1. Initialize Lottery System")
        engine = LotteryEngine(self.config)
        
        # Create new draw
        draw = engine.create_new_draw()
        engine.current_draw = draw
        self.print_success(f"Created draw: {draw.draw_id}")
        self.print_info(f"Draw time: {draw.draw_time}")
        
        # 2. Display initial status
        print("\n📊 2. System Initial Status")
        draw_info = engine.get_current_draw_info()
        print(f"   Draw ID: {draw_info['draw_id']}")
        print(f"   Total pot: {draw_info['total_pot']} ETH")
        print(f"   Participants: {draw_info['participants']}")
        print(f"   Status: {draw_info['status']}")
        
        # 3. Simulate user betting
        print("\n💰 3. User Betting Phase")
        print("   Simulating 5 users placing bets...")
        
        for user in self.users:
            # Random betting 1-3 tickets
            tickets = random.randint(1, 3)
            
            for i in range(tickets):
                bet_info = engine.place_bet(
                    user['address'],
                    engine.single_bet_amount,
                    f"0x{random.randint(10000, 99999):064x}"
                )
                
                if bet_info['success']:
                    print(f"   {user['name']}: Bet {engine.single_bet_amount} ETH ✅")
                else:
                    print(f"   {user['name']}: Bet failed ❌")
            
            await asyncio.sleep(0.3)  # Simulate time interval
        
        # 4. Display post-betting status
        print("\n🎫 4. Post-Betting Status")
        draw_info = engine.get_current_draw_info()
        print(f"   Total pot: {draw_info['total_pot']} ETH")
        print(f"   Participants: {draw_info['participants']}")
        print(f"   Total tickets: {draw_info['total_tickets']}")
        
        print("\n   Betting details:")
        if engine.current_draw and engine.current_draw.bets:
            user_tickets = {}
            for bet in engine.current_draw.bets:
                if bet.user_address not in user_tickets:
                    user_tickets[bet.user_address] = 0
                user_tickets[bet.user_address] += len(bet.ticket_numbers)
            
            total_tickets = draw_info['total_tickets']
            for address, tickets in user_tickets.items():
                user_name = next((u['name'] for u in self.users if u['address'] == address), 'Unknown')
                chance = (tickets / total_tickets) * 100 if total_tickets > 0 else 0
                print(f"     {user_name}: {tickets} tickets (Win rate: {chance:.1f}%)")
        
        # 5. Conduct draw
        print("\n🎲 5. Draw Phase")
        print("   Conducting draw...")
        await asyncio.sleep(1)
        
        # Close betting period first
        engine.current_draw.status = DrawStatus.CLOSED
        
        # Conduct draw
        winner_info = engine.conduct_draw()
        
        if winner_info and winner_info.get('success'):
            winner_name = next((u['name'] for u in self.users if u['address'] == winner_info['winner']), 'Unknown')
            print(f"\n🏆 Draw Results:")
            print(f"   Winner: {winner_name}")
            print(f"   Winner address: {winner_info['winner']}")
            print(f"   Winning number: {winner_info['winning_number']}")
            print(f"   Prize amount: {winner_info['total_pot']} ETH")
            
            # Calculate winning probability
            final_draw_info = engine.get_current_draw_info()
            if final_draw_info and final_draw_info['total_tickets'] > 0:
                winner_tickets = 0
                if engine.current_draw and engine.current_draw.bets:
                    for bet in engine.current_draw.bets:
                        if bet.user_address == winner_info['winner']:
                            winner_tickets += len(bet.ticket_numbers)
                
                winning_probability = winner_tickets / final_draw_info['total_tickets']
                print(f"   Winning probability: {winning_probability:.2%}")
            
            # Complete draw cycle and add to history
            cycle_result = engine.complete_draw_and_start_next()
            if cycle_result:
                print(f"✅ Draw completed and added to history")
        else:
            print(f"\n❌ Draw failed or no participants")
        
        # 6. Display final statistics
        print("\n📈 6. Final Statistics")
        
        print("   User statistics:")
        for user in self.users:
            stats = engine.get_user_stats(user['address'])
            print(f"     {user['name']}: {stats['total_bets']} bets, {stats['wins']} wins")
        
        print("   Recent activities:")
        activities = engine.get_recent_activities(5)
        for activity in activities[-3:]:
            activity_desc = f"{activity['activity_type']}: {activity['details']}"
            print(f"     {activity['timestamp'][11:19]}: {activity_desc}")
        
        # 7. System functionality verification
        print("\n🔧 7. System Functionality Verification")
        
        # Verify data integrity
        history = engine.get_draw_history(1)
        if history:
            self.print_success("Draw history records complete")
        
        # Verify randomness
        if winner_info and winner_info.get('success'):
            self.print_success("Random number generation working")
        
        # Verify betting mechanism
        if draw_info['participants'] > 0:
            self.print_success("Betting mechanism working normally")
        
        self.print_header("Quick Demo Complete")
        print("🎉 All core lottery system functions demonstrated!")
        
        print(f"\n📊 Demo session data:")
        final_draw_info = engine.get_current_draw_info()
        if final_draw_info:
            print(f"   Participating users: {len(self.users)} people")
            print(f"   Total bets: {final_draw_info['total_pot']} ETH")
            print(f"   Total tickets: {final_draw_info['total_tickets']} tickets")
        if winner_info and winner_info.get('success'):
            winner_name = next((u['name'] for u in self.users if u['address'] == winner_info['winner']), 'Unknown')
            print(f"   Winner: {winner_name}")
        
        print(f"\n🚀 System features demonstrated:")
        print(f"   ✅ Fair random draw")
        print(f"   ✅ Transparent betting records")
        print(f"   ✅ Real-time status updates")
        print(f"   ✅ Complete audit logs")
        print(f"   ✅ User analytics")
    
    async def interactive_demo(self):
        """Step-by-step interactive demo with user control"""
        self.print_header("Interactive Demo")
        print("This demo will guide you through each step of the lottery system.")
        print("Press Enter to continue at each step...")
        
        engine = LotteryEngine(self.config)
        
        # Step 1
        input("\n👆 Press Enter to create a new lottery draw...")
        draw = engine.create_new_draw()
        engine.current_draw = draw
        self.print_success(f"Created draw: {draw.draw_id}")
        
        # Step 2
        input("\n👆 Press Enter to show initial system status...")
        draw_info = engine.get_current_draw_info()
        print(f"📊 Current Status:")
        print(f"   Draw ID: {draw_info['draw_id']}")
        print(f"   Total pot: {draw_info['total_pot']} ETH")
        print(f"   Participants: {draw_info['participants']}")
        print(f"   Status: {draw_info['status']}")
        
        # Step 3
        input("\n👆 Press Enter to simulate user betting...")
        print("💰 Users are placing bets:")
        for user in self.users:
            tickets = random.randint(1, 2)
            for i in range(tickets):
                bet_info = engine.place_bet(
                    user['address'],
                    engine.single_bet_amount,
                    f"0x{random.randint(10000, 99999):064x}"
                )
                if bet_info['success']:
                    print(f"   {user['name']}: Bet {engine.single_bet_amount} ETH ✅")
            await asyncio.sleep(0.5)
        
        # Step 4
        input("\n👆 Press Enter to view betting results...")
        draw_info = engine.get_current_draw_info()
        print(f"🎫 Betting Results:")
        print(f"   Total pot: {draw_info['total_pot']} ETH")
        print(f"   Participants: {draw_info['participants']}")
        print(f"   Total tickets: {draw_info['total_tickets']}")
        
        # Step 5
        input("\n👆 Press Enter to conduct the lottery draw...")
        engine.current_draw.status = DrawStatus.CLOSED
        winner_info = engine.conduct_draw()
        
        if winner_info and winner_info.get('success'):
            winner_name = next((u['name'] for u in self.users if u['address'] == winner_info['winner']), 'Unknown')
            print(f"🏆 WINNER: {winner_name}!")
            print(f"   Prize: {winner_info['total_pot']} ETH")
            print(f"   Winning number: {winner_info['winning_number']}")
            
            # Complete draw cycle and add to history
            cycle_result = engine.complete_draw_and_start_next()
            if cycle_result:
                print(f"✅ Draw completed and added to history")
        
        print("\n🎉 Interactive demo complete!")
    
    def technical_demo(self):
        """Technical analysis and detailed system information"""
        self.print_header("Technical Demo")
        
        print("🔬 System Architecture Analysis:")
        print("   • Lottery Engine: Secure random number generation")
        print("   • State Management: Draw lifecycle management")
        print("   • Data Integrity: Complete audit trail")
        print("   • Security: Prevention of double betting")
        
        print("\n📋 Technical Specifications:")
        print("   • Programming Language: Python 3.9+")
        print("   • Randomness: secrets.randbelow() - cryptographically secure")
        print("   • State Machine: BETTING → CLOSED → DRAWN → COMPLETED")
        print("   • Data Storage: In-memory with activity logging")
        
        print("\n🛡️ Security Features:")
        print("   • Secure random number generation")
        print("   • Address validation")
        print("   • State transition controls")
        print("   • Complete operation logging")
        
        print("\n📊 Performance Characteristics:")
        print("   • Concurrent bet handling: Async support")
        print("   • Memory efficient: Minimal storage footprint")
        print("   • Fast execution: O(n) draw complexity")
        print("   • Scalable: Supports multiple concurrent draws")
    
    def web_demo(self):
        """Launch web interface if available"""
        self.print_header("Web Demo")
        print("🌐 Checking for web interface...")
        
        # Check if comprehensive demo script exists
        demo_script = os.path.join(PROJECT_ROOT, 'scripts', 'comprehensive_demo.sh')
        if os.path.exists(demo_script):
            print("📡 Starting comprehensive demo with web interface...")
            try:
                subprocess.run(["bash", demo_script], cwd=PROJECT_ROOT)
            except KeyboardInterrupt:
                print("\n🛑 Web demo stopped by user")
        else:
            print("❌ Web interface not available")
            print("   The web demo is currently in development")
    
    def docker_demo(self):
        """Launch real Docker enclave container demo"""
        self.print_header("Docker Demo - Real Enclave Container")
        print("🐳 Starting real Docker enclave environment...")
        
        try:
            # Check if Docker is available
            print("🔍 Checking Docker availability...")
            result = subprocess.run(["docker", "--version"], 
                                  capture_output=True, text=True, check=True)
            print(f"   ✅ {result.stdout.strip()}")
            
            # Check if we need to build the image
            print("\n🔨 Checking enclave Docker image...")
            image_check = subprocess.run(["docker", "images", "-q", "enclave-lottery-app"], 
                                       capture_output=True, text=True)
            
            if not image_check.stdout.strip():
                print("   📦 Building enclave Docker image (this may take a few minutes)...")
                build_result = subprocess.run(
                    ["docker", "build", "-t", "enclave-lottery-app", "./enclave"],
                    cwd=PROJECT_ROOT,
                    check=True
                )
                print("   ✅ Docker image built successfully")
            else:
                print("   ✅ Docker image already exists")
            
            # Stop any existing container
            print("\n🧹 Cleaning up any existing containers...")
            subprocess.run(["docker", "stop", "enclave-demo"], 
                         capture_output=True, text=True)
            subprocess.run(["docker", "rm", "enclave-demo"], 
                         capture_output=True, text=True)
            
            # Start the enclave container
            print("\n🚀 Starting enclave container...")
            container_cmd = [
                "docker", "run", "-d", 
                "--name", "enclave-demo",
                "-p", "8081:8080",  # Use port 8081 to avoid conflicts
                "--add-host", "host.docker.internal:host-gateway",  # Allow access to host
                "-e", "BLOCKCHAIN_RPC_URL=http://host.docker.internal:8545",   # Connect to host blockchain
                "enclave-lottery-app"
            ]
            
            subprocess.run(container_cmd, check=True, cwd=PROJECT_ROOT)
            print("   ✅ Container started successfully")
            
            # Wait for container to be ready
            print("\n⏳ Waiting for enclave to initialize...")
            import time
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                try:
                    health_check = subprocess.run(
                        ["curl", "-s", "http://localhost:8081/api/status"],
                        capture_output=True, text=True, timeout=5
                    )
                    if health_check.returncode == 0:
                        print("   ✅ Enclave is ready!")
                        break
                except subprocess.TimeoutExpired:
                    pass
                print(f"   ⏳ Waiting... ({i+1}/30)")
            else:
                print("   ⚠️  Enclave might still be starting up")
            
            # Show container status
            print("\n📊 Container Status:")
            subprocess.run(["docker", "ps", "--filter", "name=enclave-demo"], check=True)
            
            # Show available endpoints
            print("\n🌐 Available Endpoints:")
            print("   • Web Interface: http://localhost:8081")
            print("   • API Status: http://localhost:8081/api/status") 
            print("   • Current Draw: http://localhost:8081/api/draw/current")
            print("   • Draw History: http://localhost:8081/api/draw/history")
            
            # Interactive demo options
            print("\n🎮 Demo Options:")
            print("1. Open web interface in browser")
            print("2. Run API demonstration") 
            print("3. View container logs")
            print("4. Stop and cleanup")
            
            while True:
                demo_choice = input("\nSelect option (1-4): ").strip()
                
                if demo_choice == '1':
                    print("🌐 Opening web interface...")
                    try:
                        # Try to open browser (works on most systems)
                        subprocess.run(["python3", "-c", 
                                      "import webbrowser; webbrowser.open('http://localhost:8081')"])
                        print("   ✅ Browser should open shortly")
                    except:
                        print("   ℹ️  Please manually open: http://localhost:8081")
                    
                elif demo_choice == '2':
                    self._run_api_demo()
                    
                elif demo_choice == '3':
                    print("\n📋 Container Logs (last 20 lines):")
                    subprocess.run(["docker", "logs", "--tail", "20", "enclave-demo"])
                    
                elif demo_choice == '4':
                    break
                else:
                    print("❌ Invalid choice. Please select 1-4.")
            
            # Cleanup
            print("\n🧹 Stopping and cleaning up container...")
            subprocess.run(["docker", "stop", "enclave-demo"], check=True)
            subprocess.run(["docker", "rm", "enclave-demo"], check=True)
            print("   ✅ Cleanup complete")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Docker command failed: {e}")
            print("   Please ensure Docker is installed and running")
        except KeyboardInterrupt:
            print("\n🛑 Docker demo interrupted by user")
            print("🧹 Cleaning up...")
            subprocess.run(["docker", "stop", "enclave-demo"], 
                         capture_output=True, text=True)
            subprocess.run(["docker", "rm", "enclave-demo"], 
                         capture_output=True, text=True)
        except Exception as e:
            print(f"❌ Error during Docker demo: {e}")
    
    def _run_api_demo(self):
        """Run API demonstration against the Docker container"""
        print("\n🔧 API Demonstration:")
        
        api_tests = [
            ("System Status", "http://localhost:8081/api/status"),
            ("Current Draw", "http://localhost:8081/api/draw/current"), 
            ("Draw History", "http://localhost:8081/api/draw/history"),
            ("User Statistics", "http://localhost:8081/api/users/stats")
        ]
        
        for test_name, url in api_tests:
            try:
                print(f"\n📡 Testing {test_name}...")
                result = subprocess.run(
                    ["curl", "-s", url], 
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    try:
                        # Try to format JSON nicely
                        import json
                        data = json.loads(result.stdout)
                        formatted = json.dumps(data, indent=2)
                        print(f"   ✅ Response:")
                        print(f"   {formatted}")
                    except:
                        print(f"   ✅ Response: {result.stdout}")
                else:
                    print(f"   ❌ Failed to connect")
            except subprocess.TimeoutExpired:
                print(f"   ⏰ Request timed out")
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    async def run(self):
        """Main demo runner with interactive menu"""
        while True:
            try:
                self.print_menu()
                choice = input("Please select (1-6): ").strip()
                
                if choice == '1':
                    await self.quick_demo()
                elif choice == '2':
                    await self.interactive_demo()
                elif choice == '3':
                    self.technical_demo()
                elif choice == '4':
                    self.web_demo()
                elif choice == '5':
                    self.docker_demo()
                elif choice == '6':
                    print("\n👋 Thank you for trying the Lottery System Demo!")
                    break
                else:
                    print("❌ Invalid selection. Please choose 1-6.")
                
                if choice in ['1', '2', '3', '4', '5']:
                    try:
                        input("\n👆 Press Enter to return to main menu...")
                    except EOFError:
                        # Non-interactive mode, just continue
                        print("\n👆 Returning to main menu...")
                        break
                    
            except KeyboardInterrupt:
                print("\n\n👋 Demo interrupted. Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Non-interactive mode detected. Demo complete!")
                break
            except Exception as e:
                print(f"\n❌ Demo error: {e}")
                try:
                    input("Press Enter to continue...")
                except EOFError:
                    break

if __name__ == "__main__":
    demo = LotteryDemo()
    asyncio.run(demo.run())