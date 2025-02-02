import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import tkinter as tk
from tkinter import scrolledtext
from matplotlib.collections import PathCollection

from .node import PastryNode
from .helper_functions import hash_key


WIDTH = 1680
HEIGHT = 720


class PastryDashboard:
    def __init__(self, network, main_window):
        self.network = network
        self.main_window = main_window
        self.selected_node = None
        self.root = tk.Tk()
        self.root.title("Pastry GUI")
        self.root.geometry(f"{WIDTH}x{HEIGHT}")

        # Ensure cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Setup main layout
        self.setup_widgets()

    def on_close(self):
        """Shut down Pastry network before closing GUI."""
        print("Shutting down network...")
        for node in self.network.nodes.values():
            node.running = False

        # Stop Tkinter main loop
        self.root.quit()  # Exit the event loop
        self.root.destroy()  # Destroy the GUI window
        self.main_window.deiconify()  # Show the main window again

    def setup_widgets(self):
        # Left frame for control buttons
        control_width = WIDTH // 8
        control_frame = tk.Frame(self.root, width=control_width, height=HEIGHT, bg="lightgray")
        control_frame.pack(side=tk.LEFT, fill=tk.Y)
        control_frame.pack_propagate(False)  # Prevents resizing

        # Show Pastry button
        self.show_pastry_button = tk.Button(
            control_frame,
            text="Show Pastry",
            command=self.show_pastry_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.show_pastry_button.pack(pady=10, padx=10)

        # Show KD Tree button
        self.show_kd_tree_button = tk.Button(
            control_frame,
            text="Show KD Tree",
            command=self.show_kd_tree_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.show_kd_tree_button.pack(pady=10, padx=10)

        # Node join button
        self.node_join_button = tk.Button(
            control_frame,
            text="Node Join",
            command=self.node_join_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.node_join_button.pack(pady=10, padx=10)

        # Node leave button
        self.node_leave_button = tk.Button(
            control_frame,
            text="Node Leave",
            command=self.node_leave_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.node_leave_button.pack(pady=10, padx=10)

        # Node leave unexpected button
        self.node_leave_unexpected_button = tk.Button(
            control_frame,
            text="Node Leave Unexpected",
            command=self.node_leave_unexpected_gui,
            width=15,
            height=2,
            font=("Arial", 14),
            wraplength=150,
            justify=tk.CENTER,
        )
        self.node_leave_unexpected_button.pack(pady=10, padx=10)

        # Insert key button
        self.insert_key_button = tk.Button(
            control_frame,
            text="Insert Key",
            command=self.insert_key_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.insert_key_button.pack(pady=10, padx=10)

        # Update key button
        self.update_key_button = tk.Button(
            control_frame,
            text="Update Key",
            command=self.update_key_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.update_key_button.pack(pady=10, padx=10)

        # Delete key button
        self.delete_key_button = tk.Button(
            control_frame,
            text="Delete Key",
            command=self.delete_key_gui,
            width=15,
            height=2,
            font=("Arial", 14),
        )
        self.delete_key_button.pack(pady=10, padx=10)

        # Center frame for visualizations
        viz_width = HEIGHT
        self.viz_frame = tk.Frame(self.root, width=viz_width, height=HEIGHT)
        self.viz_frame.pack(side=tk.LEFT, fill=tk.Y)

        fig_width = viz_width / 100
        fig_height = HEIGHT / 100
        self.fig = plt.figure(figsize=(fig_width, fig_height))

        # Topology visualization (Bottom)
        topology_pad = 0.05

        self.topology_x = topology_pad
        self.topology_y = topology_pad
        self.topology_width = (
            1 - self.topology_x - topology_pad
        )  # 100% of the fig width - the padding left and right
        self.topology_height = 1 / 4 - self.topology_y  # 1/4 of the fig height - the padding
        self.ax_topology = self.fig.add_axes(
            [self.topology_x, self.topology_y, self.topology_width, self.topology_height]
        )

        self.ax_topology.set_xlim(0, 1)
        self.ax_topology.set_ylim(-0.1, 0.1)
        self.ax_topology.set_xticks(np.linspace(0, 1, 11))
        self.ax_topology.set_yticks([])
        self.ax_topology.set_title("Pastry Network Topology")

        # Create main visualization (Pastry Ring)
        ring_pad_bottom = 0.03
        ring_pad_top = 0.05
        topology_x_mid = (self.topology_x + (self.topology_x + self.topology_width)) / 2
        topology_x_quarter = (self.topology_x + topology_x_mid) / 2
        topology_x_eighth = (self.topology_x + topology_x_quarter) / 2

        self.ring_x = (self.topology_x + topology_x_eighth) / 2
        ring_x_width = self.ring_x - self.topology_x
        self.ring_y = self.topology_y + self.topology_height + ring_pad_bottom
        self.ring_width = self.topology_width - 2 * ring_x_width
        self.ring_height = 1 - self.topology_height - topology_pad - ring_pad_bottom - ring_pad_top

        self.ax_ring = self.fig.add_axes(
            [self.ring_x, self.ring_y, self.ring_width, self.ring_height]
        )

        self.ax_ring.set_xlim(-1.2, 1.2)
        self.ax_ring.set_ylim(-1.2, 1.2)
        self.ax_ring.set_xticks([])
        self.ax_ring.set_yticks([])
        self.ax_ring.set_title("Pastry Overlay Network Visualization")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.Y, expand=True)
        self.pastry_node_pick_event_id = self.canvas.mpl_connect("pick_event", self.on_node_pick)

        # Right frame for node info
        self.info_frame = tk.Frame(self.root)
        self.info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        # Configure a grid layout: row 0 for node info, row 1 for the review panel
        self.info_frame.grid_rowconfigure(0, weight=3)
        self.info_frame.grid_rowconfigure(1, weight=1)
        self.info_frame.grid_columnconfigure(0, weight=1)

        node_info_label = tk.Label(self.info_frame, text="Node Information", font=("Arial", 14))
        node_info_label.grid(row=0, column=0, sticky="n", padx=5, pady=5)
        self.info_text = scrolledtext.ScrolledText(
            self.info_frame, wrap=tk.WORD, width=30, height=50
        )
        self.info_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=(35, 0))

    def visualize_network(self, threshold=0.3):
        """
        Visualizes the Pastry network by placing nodes on a circular ring
        based on their 4-digit hex ID. Lower values are at the top (12 o'clock),
        and values increase clockwise.

        Nodes that are too close together will be moved slightly.
        """
        if not self.network.nodes:
            print("No nodes in the network to visualize.")
            return

        # Convert node IDs from hex to integers for sorting
        sorted_nodes = sorted(self.network.nodes.keys(), key=lambda x: int(x, 16))

        self.ax_ring.clear()
        self.ax_ring.set_title("Pastry Overlay Network Visualization")
        self.ax_ring.spines["top"].set_visible(False)
        self.ax_ring.spines["bottom"].set_visible(False)
        self.ax_ring.spines["left"].set_visible(False)
        self.ax_ring.spines["right"].set_visible(False)

        self.ax_ring.set_xticks([])  # Remove x-axis ticks
        self.ax_ring.set_yticks([])  # Remove y-axis ticks

        if not self.network.nodes:
            return

        radius = 1
        circle = plt.Circle((0, 0), radius, color="lightgray", fill=False)
        self.ax_ring.add_patch(circle)

        placed_positions = {}  # Store positions for overlap checking

        # Arrange nodes based on their numerical value
        for node_id in sorted_nodes:
            angle = 2 * np.pi * (int(node_id, 16) / 0xFFFF)
            base_x, base_y = radius * np.sin(angle), radius * np.cos(angle)

            # Check for overlap within the threshold distance
            shift_angle = np.radians(6.5)  # Base shift distance
            for close_node_id in placed_positions.keys():

                dist = np.linalg.norm(
                    [
                        base_x - placed_positions[close_node_id][0],
                        base_y - placed_positions[close_node_id][1],
                    ]
                )
                if dist < threshold:
                    # Move to the right clockwise slightly
                    angle += shift_angle
                    base_x = radius * np.sin(angle)
                    base_y = radius * np.cos(angle)

            placed_positions[node_id] = (base_x, base_y)

            node_plot = self.ax_ring.scatter(base_x, base_y, color="lightblue", s=100, picker=True)
            node_plot.set_gid(node_id)  # Store the node ID in the plot

            text_offset = 0.05
            text_x = (radius + text_offset) * np.sin(angle)
            text_y = (radius + text_offset) * np.cos(angle)
            ha = "center"
            va = "center"
            if text_x > 0:  # Right half of the circle
                ha = "left"
            else:  # Left half of the circle
                ha = "right"
            self.ax_ring.text(
                text_x,
                text_y,
                node_id,
                fontsize=10,
                ha=ha,
                va=va,
                color="black",
            )

        self.canvas.draw()

    def visualize_topology(self):
        """
        Visualizes the Pastry network by placing nodes as points on a horizontal line [0,1]
        based on the nodes' position attribute (which is a float in [0,1]).
        """
        if not self.network.nodes:
            print("No nodes in the network to visualize.")
            return
        # Draw a horizontal line to represent the topology
        self.ax_topology.clear()
        self.ax_topology.plot([0, 1], [0, 0], color="gray", linestyle="--")
        self.ax_topology.set_xlim(0, 1)
        self.ax_topology.set_ylim(-0.1, 0.1)  # Small height since it's a 1D layout
        self.ax_topology.set_xticks(np.linspace(0, 1, 11))
        self.ax_topology.set_yticks([])
        self.ax_topology.spines["top"].set_visible(True)
        self.ax_topology.spines["bottom"].set_visible(True)
        self.ax_topology.spines["left"].set_visible(True)
        self.ax_topology.spines["right"].set_visible(True)
        self.ax_topology.set_title("Pastry Network Topology")

        # Sort nodes by position for a structured layout
        sorted_nodes = sorted(self.network.nodes.values(), key=lambda node: node.position)

        # Plot each node at its position on the horizontal line
        for node in sorted_nodes:
            x = node.position

            node_plot = self.ax_topology.scatter(x, 0, color="lightblue", s=100, picker=True)
            node_plot.set_gid(node.node_id)  # Store the node ID in the plot
            # self.ax_topology.plot(x, 0, "o", color="lightblue", markersize=10)  # Node as a point
            self.ax_topology.text(
                x,
                0.025,
                node.node_id,
                fontsize=10,
                ha="center",
                va="center",
                color="black",
            )  # Label above

        # Draw a horizontal line to represent the topology
        self.ax_topology.plot([0, 1], [0, 0], color="gray", linestyle="--")

        self.canvas.draw()

    def on_node_pick(self, event):
        if isinstance(event.artist, PathCollection):
            node_id = event.artist.get_gid()
            selected_node = self.network.nodes.get(node_id)
            if selected_node:
                self.selected_node = selected_node
                self.update_info_panel(selected_node)

    def update_info_panel(self, node):
        """Print node information in the right panel."""
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)

        # Insert the formatted node state with monospace font
        self.info_text.insert(tk.END, node.get_state())

        # Ensure text uses a fixed-width font for proper alignment
        self.info_text.config(font=("Courier", 11), state=tk.DISABLED)

    def node_join_gui(self):
        def submit(event=None):  # Accept event argument for key binding
            nonlocal new_node_id
            new_node_id = entry.get().strip().lower()
            join_window.destroy()

        join_window = tk.Toplevel(self.root)
        join_window.title("Node Join")
        join_window.geometry("300x150")

        tk.Label(join_window, text="Enter 4-digit hex ID:", font=("Arial", 14)).pack(pady=10)

        entry = tk.Entry(join_window, width=20)
        entry.pack(pady=2)
        entry.focus_set()  # Set focus to the entry field

        # Bind Enter key to submit function
        entry.bind("<Return>", submit)

        tk.Button(join_window, text="Submit", command=submit, font=("Arial", 12)).pack(pady=10)

        new_node_id = None

        join_window.grab_set()
        self.root.wait_window(join_window)

        if not new_node_id:
            print("\nNode join canceled.")
            return

        if len(new_node_id) != 4 or not all(c in "0123456789abcdefABCDEF" for c in new_node_id):
            print("Invalid Node ID.")
            return

        node = PastryNode(self.network, node_id=new_node_id)
        print(f"\nAdding new node with ID: {node.node_id} to the network.")
        node.start_server()
        self.network.node_join(node)
        self.show_pastry_gui()

    def node_leave_gui(self):
        if self.selected_node is None:
            print("No node selected.")
            return

        print("Node is leaving gracefully...")

        leaving_node_id = self.selected_node.node_id

        leave_response = self.network.leave(leaving_node_id)
        if leave_response and "hops" in leave_response:
            print(f"Hops during NODE_LEAVE for {leaving_node_id}: {len(leave_response['hops'])}")
        else:
            print(f"Failed to retrieve hops for NODE_LEAVE {leaving_node_id}.")

        self.show_pastry_gui()

    def node_leave_unexpected_gui(self):
        if self.selected_node is None:
            print("No node selected.")
            return

        print("Node left unexpectedly.")
        leaving_node_id = self.selected_node.node_id

        self.network.leave_unexpected(leaving_node_id)

        self.show_pastry_gui()

    def show_pastry_gui(self):
        """Displays the Pastry ring and topology."""

        if hasattr(self, "has_more_countries"):
            del self.has_more_countries

        # Remove the temporary KD-Tree plot if it exists
        if hasattr(self, "ax_kd_tree"):
            self.ax_kd_tree.remove()
            del self.ax_kd_tree

        # Disconnect the KD-Tree pick event if active
        if hasattr(self, "kd_tree_pick_event_id"):
            self.canvas.mpl_disconnect(self.kd_tree_pick_event_id)
            del self.kd_tree_pick_event_id  # Remove reference

        if hasattr(self, "review_text"):
            self.review_text.destroy()
            del self.review_text

        # Clear all widgets from the root window
        for widget in self.root.winfo_children():
            widget.destroy()

        # Reinitialize the GUI
        self.setup_widgets()

        # Redraw both visualizations
        self.visualize_network()
        self.visualize_topology()
        if self.selected_node and self.selected_node in self.network.nodes.values():
            self.update_info_panel(self.selected_node)
        else:
            # Clear the info panel text
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.config(state=tk.DISABLED)

    def show_kd_tree_gui(self):
        """Displays the KD Tree of the selected node if available."""
        if self.selected_node is None:
            print("No node selected.")
            return

        # If the node has only one country, don't show the country selection window
        if hasattr(self, "has_more_countries") and not self.has_more_countries:
            print("KD Tree is already displayed.")
            return

        if hasattr(self.selected_node, "kd_tree") and self.selected_node.kd_tree:
            # Open a dialog box to let the user select a unique country
            def on_select(event=None):
                nonlocal selected_country
                selected_country = country_var.get()
                if selected_country:
                    if hasattr(self, "ax_kd_tree"):
                        self.ax_kd_tree.clear()
                        self.ax_kd_tree.set_xticks([])
                        self.ax_kd_tree.set_yticks([])
                        self.ax_kd_tree.set_zticks([])
                        self.canvas.mpl_disconnect(self.kd_tree_pick_event_id)
                        del self.kd_tree_pick_event_id  # Remove reference
                    selection_window.unbind("<Return>")
                    selection_window.destroy()

            selection_window = tk.Toplevel(self.root)
            selection_window.title("Select Country")
            selection_window.geometry("300x200")

            # Make the selection window appear above the main window
            selection_window.transient(self.root)

            # Make the selection window modal so that it captures all input
            selection_window.grab_set()

            # Direct the keyboard focus to the selection window
            selection_window.focus_set()

            tk.Label(selection_window, text="Select a country:", font=("Arial", 14)).pack(pady=10)

            # Get unique countries from the KD Tree of the selected node
            unique_country_keys, unique_countries = self.network.nodes[
                self.selected_node.node_id
            ].kd_tree.get_unique_country_keys()

            # If there are more than 2 unique countries, update the "Show KD Tree" button
            if len(unique_countries) >= 2:
                self.show_kd_tree_button.config(text="Choose Country")
                self.has_more_countries = True
            else:
                self.show_kd_tree_button.config(text="Show KD Tree")
                self.has_more_countries = False

            country_var = tk.StringVar(selection_window)
            if unique_countries:
                country_var.set(unique_countries[0])  # First country as default

            dropdown = tk.OptionMenu(selection_window, country_var, *unique_countries)
            dropdown.config(font=("Arial", 12))
            dropdown["menu"].config(font=("Arial", 12))
            dropdown.pack(pady=5)

            # Add a button to confirm selection
            tk.Button(selection_window, text="OK", command=on_select, font=("Arial", 12)).pack(
                pady=10
            )

            # Bind Enter key to select action
            selection_window.bind("<Return>", on_select)

            selected_country = None

            selection_window.grab_set()
            self.root.wait_window(selection_window)

            if not selected_country:
                print("Country selection canceled.")
                del self.has_more_countries
                return

            # Get the key for the selected country
            selected_country_key = unique_country_keys[unique_countries.index(selected_country)]

            # Get points and reviews for the selected country
            points, reviews = self.network.nodes[self.selected_node.node_id].kd_tree.get_points(
                selected_country_key
            )

            # Clear the ring plot
            self.ax_ring.clear()
            self.ax_ring.set_xticks([])
            self.ax_ring.set_yticks([])

            # Clear the topology plot
            self.ax_topology.clear()
            self.ax_topology.set_xticks([])
            self.ax_topology.set_yticks([])
            self.ax_topology.spines["top"].set_visible(False)
            self.ax_topology.spines["bottom"].set_visible(False)
            self.ax_topology.spines["left"].set_visible(False)
            self.ax_topology.spines["right"].set_visible(False)

            # Create a scrollable review panel below the node information panel
            if not hasattr(self, "review_text"):
                # Decrease node info panel height
                self.info_text.config(height=25)

                # Setup review panel
                review_label = tk.Label(
                    self.info_frame, text="Review for selected point", font=("Arial", 14)
                )
                review_label.grid(row=1, column=0, sticky="n", padx=5, pady=5)
                self.review_text = scrolledtext.ScrolledText(
                    self.info_frame, wrap=tk.WORD, width=30, height=5
                )
                self.review_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=(35, 0))

            else:
                # If the review panel already exists, clear it
                self.review_text.config(state=tk.NORMAL)
                self.review_text.delete(1.0, tk.END)
                self.review_text.config(state=tk.DISABLED)

            self.ax_kd_tree = self.fig.add_subplot(111, projection="3d")

            # Disconnect Pastry pick event
            self.canvas.mpl_disconnect(self.pastry_node_pick_event_id)

            # Connect KD-Tree pick event and store ID
            self.kd_tree_pick_event_id = self.canvas.mpl_connect(
                "pick_event",
                lambda event: self.selected_node.kd_tree.on_pick(
                    event, points, reviews, self.review_text
                ),
            )

            # Visualize the KD Tree
            self.selected_node.kd_tree.visualize(
                self.ax_kd_tree,
                self.canvas,
                points,
                reviews,
                selected_country_key,
                selected_country,
            )

        else:
            print(f"Node {self.selected_node.node_id} does not have a KD Tree.")

    def insert_key_gui(self):
        """Insert a new key into the network."""
        if self.selected_node is None:
            print("No node selected.")
            return

        # Create a new window for inserting a new coffee shop key
        insert_window = tk.Toplevel(self.root)
        insert_window.title("Insert New Coffee Shop")
        # Increase the height slightly to accommodate the review field
        insert_window.geometry("400x350")

        # Create labels and entry fields using grid layout
        tk.Label(insert_window, text="Name:", font=("Arial", 12)).grid(
            row=0, column=0, padx=10, pady=5, sticky="e"
        )
        name_entry = tk.Entry(insert_window, font=("Arial", 12))
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(insert_window, text="Country:", font=("Arial", 12)).grid(
            row=1, column=0, padx=10, pady=5, sticky="e"
        )
        country_entry = tk.Entry(insert_window, font=("Arial", 12))
        country_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(insert_window, text="Year:", font=("Arial", 12)).grid(
            row=2, column=0, padx=10, pady=5, sticky="e"
        )
        year_entry = tk.Entry(insert_window, font=("Arial", 12))
        year_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(insert_window, text="Rating:", font=("Arial", 12)).grid(
            row=3, column=0, padx=10, pady=5, sticky="e"
        )
        rating_entry = tk.Entry(insert_window, font=("Arial", 12))
        rating_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(insert_window, text="Price (100g USD):", font=("Arial", 12)).grid(
            row=4, column=0, padx=10, pady=5, sticky="e"
        )
        price_entry = tk.Entry(insert_window, font=("Arial", 12))
        price_entry.grid(row=4, column=1, padx=10, pady=5)

        tk.Label(insert_window, text="Review:", font=("Arial", 12)).grid(
            row=5, column=0, padx=10, pady=5, sticky="ne"
        )
        # Use a Text widget for multi-line review input
        review_text = tk.Text(insert_window, font=("Arial", 12), width=30, height=4)
        review_text.grid(row=5, column=1, padx=10, pady=5)

        def submit():
            name = name_entry.get().strip()
            country = country_entry.get().strip()
            year_str = year_entry.get().strip()
            rating_str = rating_entry.get().strip()
            price_str = price_entry.get().strip()
            review = review_text.get("1.0", tk.END).strip()

            # Validate that all fields are filled
            if not (name and country and year_str and rating_str and price_str and review):
                print("All fields are required.")
                return

            try:
                year = float(year_str)
            except ValueError:
                print("Year must be a number.")
                return

            try:
                rating = float(rating_str)
            except ValueError:
                print("Rating must be a number.")
                return

            try:
                price = float(price_str)
            except ValueError:
                print("Price must be a number.")
                return

            print("\nInserting a new Coffee Shop Review:")
            print(
                f"Name: {name}, Country: {country}, Year: {year}, Rating: {rating}, Price: {price}, Review: {review}"
            )

            # Generate a key for the country (adjust this if needed)
            key = hash_key(country)
            point = [year, rating, price]
            # Insert the new key into the selected node
            self.selected_node.insert_key(key, point, review, country)

            # Close the insert window and update visualizations
            insert_window.destroy()
            self.show_pastry_gui()

        submit_button = tk.Button(insert_window, text="Submit", command=submit, font=("Arial", 12))
        submit_button.grid(row=6, column=0, columnspan=2, pady=10)
        insert_window.bind("<Return>", lambda event: submit())

    def update_key_gui(self):
        pass

    def delete_key_gui(self):
        pass
