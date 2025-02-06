import pandas as pd

from .helper_functions import *
from .chord_gui import ChordDashboard
from .node import ChordNode


class ChordNetwork:
    def __init__(self, main_window=None):
        self.nodes = {}  # Dictionary. Keys are node IDs, values are Node objects
        self.used_ports = []

        self.gui = ChordDashboard(self, main_window)

    def node_join(self, new_node):
        """
        Handles a new node joining the Chord network.
        """
        # Determine the node ID
        node_id = new_node.node_id

        # Add the node to the network
        self.nodes[node_id] = new_node

        # # Add the node's port to the node_ports dictionary
        # self.node_ports[new_node_id] = new_node.port

        if len(self.nodes) == 1:
            print(f"The network is empty. This node {node_id} is the first node.")
            return

        
        for id in self.nodes.keys():
            if self.nodes[id].running and node_id != id:
                successor_id, _ = new_node.request_find_successor(node_id, self.nodes[id], [])
                # new_node joins on successor
                new_node.join(self.nodes[successor_id])
                break

    def build(self, predefined_ids):
        """
        Build the Chord network with the specified number of nodes.
        """
        # Node Arrivals
        print("Node Arrivals")
        print("=======================")
        print(f"Adding {len(predefined_ids)} nodes to the network...")
        print("\n" + "-" * 100)
        for node_id in predefined_ids:
            node = ChordNode(self, node_id=node_id)
            print(f"Adding Node: ID = {node.node_id}")
            node.start_server()
            self.node_join(node)
            print(f"\nNode Added: ID = {node.node_id}")
            print("\n" + "-" * 100)
        print("\nAll nodes have successfully joined the network.\n")

        # Insert keys
        # Load dataset
        dataset_path = "Coffee_Reviews_Dataset/simplified_coffee.csv"
        df = pd.read_csv(dataset_path)

        # Keep only the year from the review_date column
        df["review_date"] = pd.to_datetime(df["review_date"], format="%B %Y").dt.year

        # Extract loc_country as keys
        keys = df["loc_country"].apply(hash_key)

        # Extract data points (review_date, rating, 100g_USD)
        points = df[["review_date", "rating", "100g_USD"]].to_numpy()

        # Extract reviews and other details
        reviews = df["review"].to_numpy()
        countries = df["loc_country"].to_numpy()
        names = df["name"].to_numpy()

        print("Key Insertions")
        print("=======================")
        print("\nInserting data into the network...")

        # Insert all entries
        for key, point, review, country, name in zip(keys, points, reviews, countries, names):
            print(f"\nInserting Key: {key}, Country: {country}, Name: {name}\n")
            self.insert_key(key, point, review, country)

        # Show the Chord GUI
        self.gui.show_dht_gui()
        # Run the gui main loop
        self.gui.root.mainloop()


    def insert_key(self, key, point, review, country):  
        for node_id in self.nodes.keys():
            if self.nodes[node_id].running:
                return self.nodes[node_id].insert_key(key, point, review, country)

    def delete_key(self, key):
        for node_id in self.nodes.keys():
            if self.nodes[node_id].running:
                return self.nodes[node_id].delete_key(key)  
    
    def update_key(self, key, updated_data, criteria=None):
        for node_id in self.nodes.keys():
            if self.nodes[node_id].running:
                return self.nodes[node_id].update_key(key, updated_data, criteria)
        

    def lookup(self, key, lower_bounds, upper_bounds, N):
        for node_id in self.nodes.keys():
            if self.nodes[node_id].running:
                return self.nodes[node_id].lookup(key, lower_bounds, upper_bounds, N)