"""
Simple network proxy for host server
Only forwards network requests to/from enclave
"""

import asyncio
import logging
import socket
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetworkProxy:
    """Simple network proxy for enclave communication"""
    
    def __init__(self, host_port: int = 6080, enclave_cid: int = 16, enclave_port: int = 6080):
        self.host_port = host_port
        self.enclave_cid = enclave_cid
        self.enclave_port = enclave_port
        
    async def start(self):
        """Start the network proxy server"""
        logger.info(f"Starting network proxy on port {self.host_port}")
        
        server = await asyncio.start_server(
            self._handle_client,
            '0.0.0.0',
            self.host_port
        )
        
        logger.info(f"Network proxy listening on port {self.host_port}")
        await server.serve_forever()
        
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connection"""
        client_addr = writer.get_extra_info('peername')
        logger.info(f"Client connected: {client_addr}")
        
        # Connect to enclave
        try:
            enclave_reader, enclave_writer = await asyncio.open_connection(
                family=socket.AF_VSOCK,
                proto=socket.SOCK_STREAM,
                sock=(self.enclave_cid, self.enclave_port)
            )
            
            # Start bidirectional forwarding
            await asyncio.gather(
                self._forward_data(reader, enclave_writer, "client->enclave"),
                self._forward_data(enclave_reader, writer, "enclave->client")
            )
            
        except Exception as e:
            logger.error(f"Error connecting to enclave: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {client_addr}")
            
    async def _forward_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, direction: str):
        """Forward data between client and enclave"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                    
                writer.write(data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error forwarding data ({direction}): {e}")
        finally:
            writer.close()


async def main():
    """Main entry point"""
    proxy = NetworkProxy()
    await proxy.start()


if __name__ == "__main__":
    asyncio.run(main())