import socket
import ssl
import subprocess
import threading
import re
import time
import json
import queue
import logging
from .config import load_config


class IRCBot:
    INACTIVITY_LIMIT = 300  # 5 minutes in seconds
    THREAD_COUNT_IN_POOL = 5  # threads in threadpool

    def __init__(self):
        config = load_config()
        self.host = config["host"]
        self.port = config["port"]
        self.nick = config["nick"]
        self.user = config["user"]
        self.password = config["password"]
        self.channels = config["channels"]
        self.sock = None
        self.command = "curl http://" + config["yutto_server"] + "/"
        self.tcommand = ""
        self.bilibili_flags = config["bilibili_flags"]
        self.last_activity = time.time()
        self.model = config["model"]
        self.ollama_host = config["ollama_host"]
        self.ollama_port = config["ollama_port"]
        self.ollama_server = "http://" + self.ollama_host + "/api/generate"
        self.context = []
        self.queue = queue.Queue()
        self.channel = ""
        self.lockchat = threading.Lock()
        self.pool = []
        self.in_message_queue = queue.Queue()
        # self.out_message_queue = queue.Queue()
        self.logger = logging.getLogger('albot_loger')
        self.log_file = config["log_file"]

    # Check if lost connection with server
    def check_inactivity(self):
        time.sleep(1)
        while True:
            self.logger.info("check_inactivity")
            self.logger.info(f"curtime:{time.time()}, last_activity:{self.last_activity}")
            if time.time() - self.last_activity > self.INACTIVITY_LIMIT:
                self.logger.warning("No activity detected. Reconnecting...")
                self.reconnect()
            time.sleep(20)

    def reconnect(self):
        if self.sock:
            self.logger.warning("closing sock")
            self.sock.close()
        self.logger.warning("connecting sock")

        self.connect()

    def connect(self):
        try:
            self.logger.info("connecting...")
            context = ssl.create_default_context()
            raw_socket = socket.create_connection((self.host, self.port))
            self.sock = context.wrap_socket(raw_socket, server_hostname=self.host)
            self.sock.settimeout(300)

            self.logger.info("connect success")
            self.sock.send(f"PASS {self.password}\n".encode("utf-8"))
            self.sock.send(f"NICK {self.nick}\n".encode("utf-8"))
            self.sock.send(f"USER {self.user} 0 * :Albot\n".encode("utf-8"))
            return 0
        except Exception as e:
            self.logger.error(f"Connecting to server failed: {e}")
            return 1

    def join_channels(self):
        for channel in self.channels:
            self.sock.send(f"JOIN {channel}\n".encode("utf-8"))

    def run_shell_command(self, channel, user):
        self.logger.info(f"Command:{self.tcommand}")
        self.sock.send(f"PRIVMSG {channel} :Command start, {user}! Command:{self.tcommand}\n".encode("utf-8"))
        process = subprocess.Popen(self.tcommand,
                                   shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()

        if (process.returncode == 0):
            self.sock.send(f"PRIVMSG {channel} :Command finished, {user}! Command:{self.tcommand}\n".encode("utf-8"))
        else:
            self.sock.send(f"PRIVMSG {channel} :Command failed, {user}! Command:{self.tcommand} | Return Code: {process.returncode}\n".encode("utf-8"))

        self.logger.info(f"worker for {channel} exit.")
        self.logger.info(f"Output:\n{output.decode()}")
        self.logger.info(f"Return Code: {process.returncode}")

    def gen_message_for_queue(self, channel, data):
        json.dumps({"channel": channel, "data": data})

    # Access ollama's api
    def gpt_get_worker(self, channel, user, prompt):
        # Prepare JSON payload
        payload = json.dumps({
            'model': self.model,
            'prompt': prompt,
            'context': self.context,
            'stream': True,
        })

        # Build the HTTP request manually
        request = (
            f"POST /api/generate HTTP/1.1\r\n"
            f"Host: {self.ollama_host}:{self.ollama_port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"Connection: close\r\n\r\n"
            f"{payload}"
        )

        # Make sure only one request to ollama server at a time, may change latter
        with self.lockchat:
            # Connect to the server using a socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.ollama_host, self.ollama_port))
                s.sendall(request.encode("utf-8"))

                # Make sure putting a full json binary string to queue each time
                datas = bytearray()
                try:
                    while True:
                        chunk = s.recv(1024)
                        self.logger.info(f"*recv:\n{chunk}")
                        if chunk.endswith(b'\r\n'):
                            if datas:
                                datas.extend(chunk)
                                if datas.startswith(b'HTTP') and datas.endswith(b'}\n\r\n'):
                                    header, datas = datas.split(b'\r\n\r\n', 1)
                                self.queue.put(json.dumps({"channel": channel, "user": user, "data": datas.hex()}))

                                datas.clear()
                            else:
                                if chunk.startswith(b'HTTP') and chunk.endswith(b'}\n\r\n'):
                                    header, chunk = chunk.split(b'\r\n\r\n', 1)
                                if chunk.startswith(b'0'):
                                    pass
                                else:
                                    self.queue.put(json.dumps({"channel": channel, "user": user, "data": chunk.hex()}))
                        elif chunk:
                            datas.extend(chunk)
                        else:
                            break
                except Exception as e:
                    # Handle any errors here...
                    self.logger.error(e)
                    raise e
            # Wait for self.queue to be cleared
            time.sleep(3)

    # Get ollama generated message in queue and send out
    def gpt_generate(self):
        response_part = ""
        while True:
            # Wait for message
            data = self.queue.get()

            # Parse json string
            data = json.loads(data)
            user = data["user"]
            channel = data["channel"]
            data = bytearray.fromhex(data["data"])
            self.logger.info(f"*user:\n{user}")
            self.logger.info(f"*channel:\n{channel}")
            self.logger.info(f"*data:\n{data}")
            try:
                body_part = json.loads(data.split(b'\r\n')[1])
            except Exception as e:
                self.logger.error(e)
                raise e
            self.logger.info(body_part.get('response'))
            # Chenk if ollama have said a line and then send the line
            if '\n' in body_part.get('response'):
                response_part += body_part.get('response').replace('\n\n', '')
                self.logger.info(f"*send:\n{response_part}")
                self.sock.send(f"PRIVMSG {channel} :{response_part}\n".encode("utf-8"))
                response_part = ""
            else:
                response_part += body_part.get('response')
            if body_part.get('done'):
                if response_part:
                    self.logger.info(f"*send:\n{response_part}")
                    self.sock.send(f"PRIVMSG {channel} :{response_part}\n".encode("utf-8"))
                    response_part = ""

            if 'error' in body_part:
                raise Exception(body_part['error'])

            if body_part.get('done', False):
                # Keep chat history
                self.context = body_part['context']

    def process_in_message(self):
        while True:
            response = self.in_message_queue.get()
            for channel in self.channels:
                if f"PRIVMSG {channel}" in response:

                    # Extract message
                    user = response.split("!")[0][1:]
                    message = response.split(f"PRIVMSG {channel} :")[1]
                    self.logger.info(f"{user} in {channel}: {message}")

                    # Handle message
                    if "albot" in message.lower():
                        if "albotreset" in message.lower():
                            self.context = []
                            self.sock.send(f"PRIVMSG {channel} :Albot reseted, {user}!\n".encode("utf-8"))

                        else:
                            self.sock.send(f"PRIVMSG {channel} :Albot copy, {user}!\n".encode("utf-8"))
                            # if any(s in message for s in self.bilibili_flags):
                            pattern = "|".join(re.escape(s) for s in self.bilibili_flags)
                            if re.search(pattern, message):
                                self.tcommand = self.command + "".join(message.split())
                                self.run_shell_command(channel, user)
                            else:
                                self.gpt_get_worker(channel, user, message)

    def setup_logger(self):
        # Setup log
        self.logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s|%(name)s|%(levelname)s|%(message)s'))
        self.logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s|%(name)s|%(levelname)s|%(message)s'))
        self.logger.addHandler(stream_handler)

        self.logger.info('Logger started.')

    def run(self):
        self.setup_logger()
        self.connect()
        for _ in range(self.THREAD_COUNT_IN_POOL):  # Create threads
            thread = threading.Thread(target=self.process_in_message)
            thread.start()
            self.pool.append(thread)
        thread_check_activity = threading.Thread(target=self.check_inactivity)
        thread_check_activity.start()
        thread_gpt_generate = threading.Thread(target=self.gpt_generate)
        thread_gpt_generate.start()
        while True:
            try:
                response = self.sock.recv(2048).decode("utf-8").strip()
            except Exception as e:
                #self.logger.error("recv from sock error")
                time.sleep(5)
                continue
            if response:
                self.last_activity = time.time()
                self.logger.info(response)

            # Server keep alive
            if response.startswith("PING"):
                self.sock.send(f"PONG {response.split()[1]}\n".encode("utf-8"))

            # Join channel
            if "001" in response:
                self.join_channels()

            if "PRIVMSG" in response:
                self.in_message_queue.put(response)


