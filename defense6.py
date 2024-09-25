import sys
import socket
import threading
import time
import random
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QSlider, QTextEdit, QSplitter, QProgressBar
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtMultimedia import QSound  # For playing alarm sound


class DefenseSignals(QObject):
    update_blocked_list = pyqtSignal(str)
    update_network_map = pyqtSignal(str)
    remove_node_from_map = pyqtSignal(str)  # Signal to remove a blocked node
    reset_blocked_list = pyqtSignal()  # Signal to clear the blocked machines list
    update_progress_bar = pyqtSignal(int, int)  # Update the progress bar (machine_index, num_requests)


class DefenseApp(QMainWindow):
    def __init__(self, listening_port, request_threshold):
        super().__init__()

        self.listening_port = listening_port
        self.request_threshold = request_threshold  # Request threshold for blocking
        self.request_times = {}  # Track requests per IP
        self.attacking_ips = {}  # Track the attacking IPs and their positions on the map
        self.defense_enabled = True  # Defense is enabled by default
        self.alarm_playing = False  # Track whether the alarm is already playing

        # Create a signals object to ensure thread-safe GUI updates
        self.signals = DefenseSignals()
        self.signals.update_blocked_list.connect(self.update_blocked_list_gui)
        self.signals.update_network_map.connect(self.update_network_map_gui)
        self.signals.remove_node_from_map.connect(self.remove_node_from_map_gui)
        self.signals.reset_blocked_list.connect(self.reset_blocked_list_gui)
        self.signals.update_progress_bar.connect(self.update_progress_bar_gui)

        # Load alarm sound
        self.alarm_sound = QSound("alarm.wav")  # Ensure the alarm sound file is available

        # GUI setup
        self.setWindowTitle("DDoS Defense Simulation")
        self.setGeometry(200, 200, 1200, 800)

        # Main layout
        self.main_layout = QVBoxLayout()

        # Network map visualization (1/3 of the window height)
        self.network_map_widget = pg.PlotWidget()
        self.network_map_widget.setBackground('w')
        self.network_map_widget.setTitle("Network Map")
        self.main_layout.addWidget(self.network_map_widget)
        self.main_layout.setStretch(0, 1)  # 1/3 height for the network map

        # Defense controls and blocked machines
        self.splitter = QSplitter(Qt.Horizontal)
        self.right_panel = QWidget()
        self.splitter.addWidget(self.right_panel)
        self.main_layout.addWidget(self.splitter)

        # Set layout to main window
        container = QWidget()
        container.setLayout(self.main_layout)
        self.setCentralWidget(container)

        # Initialize right panel for defense controls
        self.init_right_panel()

        # Initialize network map visualization
        self.init_network_map()

        # Start listening for incoming attack requests
        self.start_server()

    def init_right_panel(self):
        """Initialize the right panel for defense settings and blocked machines."""
        right_layout = QVBoxLayout()

        # Defense enable/disable button
        self.defense_button = QPushButton("Disable Defense")
        self.defense_button.clicked.connect(self.toggle_defense)
        right_layout.addWidget(self.defense_button)

        # Reset defense button
        self.reset_button = QPushButton("Reset Defense")
        self.reset_button.clicked.connect(self.reset_defense)
        right_layout.addWidget(self.reset_button)

        # Display blocked machines as a text area
        self.blocked_list = QTextEdit()
        self.blocked_list.setReadOnly(True)
        right_layout.addWidget(QLabel("Blocked Machines:"))
        right_layout.addWidget(self.blocked_list)

        # Add slider for request threshold
        self.label_request_threshold = QLabel('Request Threshold (within 5 seconds):')
        right_layout.addWidget(self.label_request_threshold)
        self.slider_request_threshold = QSlider(Qt.Horizontal)
        self.slider_request_threshold.setMinimum(1)
        self.slider_request_threshold.setMaximum(20)
        self.slider_request_threshold.setValue(self.request_threshold)
        self.slider_request_threshold.valueChanged.connect(self.update_request_threshold)
        right_layout.addWidget(self.slider_request_threshold)

        # Progress Bar to show requests per second (gradient from green to red)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("QProgressBar::chunk {background-color: green;}")
        right_layout.addWidget(QLabel("Request Load:"))
        right_layout.addWidget(self.progress_bar)

        self.right_panel.setLayout(right_layout)

    def toggle_defense(self):
        """Toggle defense mechanism on or off."""
        try:
            self.defense_enabled = not self.defense_enabled
            self.defense_button.setText("Enable Defense" if not self.defense_enabled else "Disable Defense")
        except Exception as e:
            print(f"Error toggling defense: {e}")

    def reset_defense(self):
        """Clear all blocked machines and reset the defense state."""
        try:
            self.request_times.clear()  # Clear all request tracking
            self.attacking_ips.clear()  # Clear all tracked attacking IPs
            self.signals.reset_blocked_list.emit()  # Clear the blocked machines list
            self.init_network_map()  # Clear the network map
        except Exception as e:
            print(f"Error resetting defense: {e}")

    def update_request_threshold(self):
        """Update the request threshold for blocking machines."""
        try:
            self.request_threshold = self.slider_request_threshold.value()
        except Exception as e:
            print(f"Error updating request threshold: {e}")

    def update_progress_bar_gui(self, machine_index, num_requests):
        """Update the progress bar in the GUI and play alarm if necessary."""
        try:
            progress = min(num_requests, 100)
            self.progress_bar.setValue(progress)
            red_ratio = progress / 100.0
            green_ratio = 1.0 - red_ratio
            color = f"rgb({int(255 * red_ratio)}, {int(255 * green_ratio)}, 0)"
            self.progress_bar.setStyleSheet(f"QProgressBar::chunk {{background-color: {color};}}")

            # Play the alarm if the load exceeds 20%
            if progress > 20 and not self.alarm_playing:
                self.alarm_sound.play()
                self.alarm_playing = True  # Ensure alarm is only played once

            # Reset alarm flag when load goes below 20%
            if progress <= 20 and self.alarm_playing:
                self.alarm_playing = False
        except Exception as e:
            print(f"Error updating progress bar: {e}")

    def start_server(self):
        """Start a TCP server to listen for incoming connections (attack requests)."""
        try:
            server_thread = threading.Thread(target=self.listen_for_attacks)
            server_thread.daemon = True  # Set thread as a daemon so it will close when the application closes
            server_thread.start()
        except Exception as e:
            print(f"Error starting server: {e}")

    def listen_for_attacks(self):
        """Listen for incoming requests and handle them."""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(("0.0.0.0", self.listening_port))
            server_socket.listen(5)

            while True:
                client_socket, client_address = server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket, client_address)).start()
        except Exception as e:
            print(f"Error listening for attacks: {e}")

    def handle_client(self, client_socket, client_address):
        """Handle incoming requests and track requests per IP."""
        try:
            data = client_socket.recv(1024).decode()  # Receive the incoming request
            forwarded_ip = self.extract_ip_from_header(data)  # Extract the 'X-Forwarded-For' IP from the header

            if forwarded_ip:
                ip = forwarded_ip  # Use the forwarded IP if available
            else:
                ip = client_address[0]  # Fallback to the actual client IP

            current_time = time.time()

            if ip not in self.request_times:
                self.request_times[ip] = []
                # Notify the network map to display this new machine
                self.signals.update_network_map.emit(ip)

            # Track the time of the request
            self.request_times[ip].append(current_time)

            # Remove requests older than 5 seconds
            self.request_times[ip] = [t for t in self.request_times[ip] if current_time - t <= 5]

            num_requests = len(self.request_times[ip])
            machine_index = list(self.request_times.keys()).index(ip)
            self.signals.update_progress_bar.emit(machine_index, num_requests)

            # Block the machine if it exceeds the request threshold and defense is enabled
            if num_requests >= self.request_threshold and self.defense_enabled:
                self.block_machine(ip)

            client_socket.close()
        except Exception as e:
            print(f"Error handling client: {e}")

    def extract_ip_from_header(self, data):
        """Extract the 'X-Forwarded-For' IP from the request header."""
        try:
            for line in data.splitlines():
                if "X-Forwarded-For" in line:
                    return line.split(":")[1].strip()
        except Exception as e:
            print(f"Error extracting IP from header: {e}")
        return None

    def block_machine(self, ip):
        """Block a machine and update the blocked machines list."""
        try:
            self.signals.update_blocked_list.emit(f"Blocked IP: {ip}")
            self.signals.remove_node_from_map.emit(ip)  # Remove the node from the map when blocked
        except Exception as e:
            print(f"Error blocking machine: {e}")

    def update_blocked_list_gui(self, ip):
        """Update the blocked machines list in the GUI (thread-safe)."""
        try:
            self.blocked_list.append(ip)
        except Exception as e:
            print(f"Error updating blocked list: {e}")

    def remove_node_from_map_gui(self, ip):
        """Remove the node from the network map when blocked."""
        try:
            if ip in self.attacking_ips:
                # Remove the node corresponding to the IP
                x_pos, y_pos = self.attacking_ips[ip]['x'], self.attacking_ips[ip]['y']
                scatter_item = self.attacking_ips[ip]['scatter']
                line_item = self.attacking_ips[ip]['line']
                self.network_map_widget.removeItem(scatter_item)  # Remove the scatter point
                self.network_map_widget.removeItem(line_item)  # Remove the line to the server
                del self.attacking_ips[ip]  # Delete the entry from the dictionary
        except Exception as e:
            print(f"Error removing node from map: {e}")

    def reset_blocked_list_gui(self):
        """Clear the blocked machines list in the GUI (thread-safe)."""
        try:
            self.blocked_list.clear()
        except Exception as e:
            print(f"Error resetting blocked list: {e}")

    def init_network_map(self):
        """Initialize network map to visualize attacks."""
        try:
            self.network_map_widget.clear()  # Clear the map
            self.server_node = pg.ScatterPlotItem(pen=pg.mkPen(width=3), brush='r', size=15)
            self.server_node.setData([0], [0])
            self.network_map_widget.addItem(self.server_node)

            # Dictionary to store the position of attacking machines on the network map
            self.attacking_ips = {}
        except Exception as e:
            print(f"Error initializing network map: {e}")

    def update_network_map_gui(self, ip):
        """Update the network map with new attacking machines (thread-safe)."""
        try:
            if ip not in self.attacking_ips:
                # Generate a random position for this machine
                x_pos = random.uniform(-10, 10)
                y_pos = random.uniform(-10, 10)

                # Add the machine to the attacking_ips dictionary with its position and map elements
                scatter = pg.ScatterPlotItem(pen=pg.mkPen(width=1), brush='b', size=10)
                scatter.setData([x_pos], [y_pos])
                self.network_map_widget.addItem(scatter)

                # Draw a line connecting the attacking machine to the server
                line = pg.PlotDataItem(pen=pg.mkPen('green', width=1))
                self.network_map_widget.addItem(line)
                line.setData([x_pos, 0], [y_pos, 0])

                # Store the elements for later removal if blocked
                self.attacking_ips[ip] = {'scatter': scatter, 'line': line, 'x': x_pos, 'y': y_pos}
        except Exception as e:
            print(f"Error updating network map: {e}")

def run_defense_gui(listening_port, request_threshold):
    """Run the defense simulation with a GUI."""
    app = QApplication(sys.argv)
    defense_app = DefenseApp(listening_port, request_threshold)
    defense_app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    listening_port = 8080  # Listening port for attack requests
    request_threshold = 5  # Number of requests per 5 seconds to block

    run_defense_gui(listening_port, request_threshold)
