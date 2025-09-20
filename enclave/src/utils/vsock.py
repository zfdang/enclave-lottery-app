"""
VSock communication utilities for AWS Nitro Enclave
"""

import asyncio
import json
import logging
import socket
import struct
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)


class VSockServer:
    """VSock server for enclave communication"""
    
    def __init__(self, port: int = 5000):
        self.port = port
        self.server: Optional[asyncio.Server] = None
        self.clients = set()
        self.message_handlers: Dict[str, Callable] = {}
        
    async def start(self):
        """Start the VSock server"""
        try:
            # Create VSock server
            self.server = await asyncio.start_server(
                self._handle_client,
                family=socket.AF_VSOCK,
                port=self.port
            )
            
            logger.info(f"VSock server started on port {self.port}")
            await self.server.serve_forever()
            
        except Exception as e:
            logger.error(f"Error starting VSock server: {e}")
            raise
            
    async def stop(self):
        """Stop the VSock server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("VSock server stopped")
            
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connection"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"VSock client connected: {client_addr}")
        
        self.clients.add(writer)
        
        try:
            while True:
                # Read message length
                length_data = await reader.readexactly(4)
                message_length = struct.unpack('!I', length_data)[0]
                
                # Read message data
                message_data = await reader.readexactly(message_length)
                message = json.loads(message_data.decode())
                
                # Process message
                response = await self._process_message(message)
                
                # Send response
                if response:
                    await self._send_message(writer, response)
                    
        except asyncio.IncompleteReadError:
            logger.info(f"VSock client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling VSock client: {e}")
        finally:
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            
    async def _send_message(self, writer: asyncio.StreamWriter, message: Dict):
        """Send message to client"""
        try:
            message_data = json.dumps(message).encode()
            length_data = struct.pack('!I', len(message_data))
            
            writer.write(length_data + message_data)
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Error sending VSock message: {e}")
            
    async def _process_message(self, message: Dict) -> Optional[Dict]:
        """Process incoming message"""
        message_type = message.get('type')
        
        if message_type in self.message_handlers:
            try:
                return await self.message_handlers[message_type](message)
            except Exception as e:
                logger.error(f"Error processing message type {message_type}: {e}")
                return {"error": f"Error processing message: {str(e)}"}
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return {"error": f"Unknown message type: {message_type}"}
            
    def register_handler(self, message_type: str, handler: Callable):
        """Register message handler"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")
        
    async def broadcast_message(self, message: Dict):
        """Broadcast message to all connected clients"""
        if not self.clients:
            return
            
        for writer in list(self.clients):
            try:
                await self._send_message(writer, message)
            except Exception as e:
                logger.error(f"Error broadcasting message: {e}")
                self.clients.discard(writer)


class VSockClient:
    """VSock client for host communication"""
    
    def __init__(self, cid: int, port: int):
        self.cid = cid  # Context ID (VMADDR_CID_HOST for host)
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
    async def connect(self):
        """Connect to VSock server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                family=socket.AF_VSOCK,
                proto=socket.SOCK_STREAM,
                sock=(self.cid, self.port)
            )
            logger.info(f"Connected to VSock server at {self.cid}:{self.port}")
            
        except Exception as e:
            logger.error(f"Error connecting to VSock server: {e}")
            raise
            
    async def disconnect(self):
        """Disconnect from VSock server"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("Disconnected from VSock server")
            
    async def send_message(self, message: Dict) -> Optional[Dict]:
        """Send message and wait for response"""
        try:
            if not self.writer:
                raise Exception("Not connected to VSock server")
                
            # Send message
            message_data = json.dumps(message).encode()
            length_data = struct.pack('!I', len(message_data))
            
            self.writer.write(length_data + message_data)
            await self.writer.drain()
            
            # Read response
            length_data = await self.reader.readexactly(4)
            response_length = struct.unpack('!I', length_data)[0]
            
            response_data = await self.reader.readexactly(response_length)
            response = json.loads(response_data.decode())
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending VSock message: {e}")
            return None


# VSock address constants
VMADDR_CID_HYPERVISOR = 0
VMADDR_CID_LOCAL = 1
VMADDR_CID_HOST = 2


def is_vsock_available() -> bool:
    """Check if VSock is available on the system"""
    try:
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        sock.close()
        return True
    except (OSError, AttributeError):
        return False