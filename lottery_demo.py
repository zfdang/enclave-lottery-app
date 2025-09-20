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
            {'name': 'Alice', 'address': '0x1111111111111111111111111111111111111111'},
            {'name': 'Bob', 'address': '0x2222222222222222222222222222222222222222'},
            {'name': 'Charlie', 'address': '0x3333333333333333333333333333333333333333'},
            {'name': 'Diana', 'address': '0x4444444444444444444444444444444444444444'},
            {'name': 'Eve', 'address': '0x5555555555555555555555555555555555555555'}
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
        print("5) ❌ Exit")
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
    
    async def run(self):
        """Main demo runner with interactive menu"""
        while True:
            try:
                self.print_menu()
                choice = input("Please select (1-5): ").strip()
                
                if choice == '1':
                    await self.quick_demo()
                elif choice == '2':
                    await self.interactive_demo()
                elif choice == '3':
                    self.technical_demo()
                elif choice == '4':
                    self.web_demo()
                elif choice == '5':
                    print("\n👋 Thank you for trying the Lottery System Demo!")
                    break
                else:
                    print("❌ Invalid selection. Please choose 1-5.")
                
                if choice in ['1', '2', '3']:
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