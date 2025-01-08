import threading
import socket
import hashlib
import pickle
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from constants import *
from helper_functions import *

# from Multidimensional_Data_Structures.kd_tree import KDTree
# from Multidimensional_Data_Structures.lsh import LSH
from sklearn.feature_extraction.text import TfidfVectorizer


class PastryNode:

    def __init__(self, network, node_id=None):
        """
        Initialize a new Pastry node with a unique ID, address, and empty data structures.
        """
        self.address = self._generate_address()  # (IP, Port)
        self.node_id = (
            node_id if node_id is not None else self._generate_id(self.address)
        )
        self.network = network  # Reference to the DHT network
        # self.kd_tree = None  # Centralized KD-Tree
        # 2D Routing Table
        self.routing_table = [
            [None for j in range(pow(2, b))] for i in range(HASH_HEX_DIGITS)
        ]
        # Leaf Set
        self.Lmin = [None for x in range(L // 2)]
        self.Lmax = [None for x in range(L // 2)]
        # Nearby nodes
        self.neighborhood_set = [None for x in range(np.floor(np.sqrt(N)).astype(int))]
        self.lock = threading.Lock()

        # Create a thread pool for handling requests to limit the number of concurrent threads
        self.thread_pool = ThreadPoolExecutor(max_workers=10)

    # Initialization Methods

    def _generate_address(self, port=None):
        """
        Generate a unique address (IP, Port) for the node.
        """
        # Simulate unique IPs in a private network range (192.168.x.x)
        ip = f"192.168.{np.random.randint(0, 256)}.{np.random.randint(1, 256)}"
        port = port or np.random.randint(1024, 65535)  # Random port if not provided
        return (ip, port)

    def _generate_id(self, address):
        """
        Generate a unique node ID by hashing the address.
        """
        address_str = f"{address[0]}:{address[1]}"
        sha1_hash = hashlib.sha1(address_str.encode()).hexdigest()
        node_id = sha1_hash[-HASH_HEX_DIGITS:]  # Take the last 128 bits
        return node_id

    # State Inspection

    def print_state(self):
        """
        Print the state of the node (ID, Address, Data Structures).
        """
        print("\n" + "-" * 100)
        print(f"Node ID: {self.node_id}")
        print(f"Address: {self.address}")
        print("\nRouting Table:")
        for row in self.routing_table:
            print(row)
        print("\nLeaf Set:")
        print(f"Lmin: {self.Lmin}")
        print(f"Lmax: {self.Lmax}")
        print("\nNeighborhood Set:")
        print(self.neighborhood_set)

    # Network Communication

    def start_server(self):
        """
        Start the server thread to listen for incoming requests.
        """
        server_thread = threading.Thread(target=self._server, daemon=True)
        server_thread.start()

    def _server(self):
        """
        Set up a socket server to handle incoming requests.
        """
        # Use loopback for actual binding
        bind_ip = "127.0.0.1"  # Bind to localhost for real communication
        bind_address = (bind_ip, self.address[1])

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(bind_address)  # Bind to localhost
            except OSError as e:
                print(f"Error binding to {bind_address}: {e}")
                return

            s.listen()
            print(
                f"\nNode {self.node_id} listening on {self.address} (bound to {bind_address})"
            )
            while True:
                conn, addr = s.accept()  # Accept incoming connection
                # Submit the connection to the thread pool for handling
                self.thread_pool.submit(self._handle_request, conn)

    def _handle_request(self, conn):
        try:
            data = conn.recv(1024)  # Read up to 1024 bytes of data
            request = pickle.loads(data)  # Deserialize the request
            operation = request["operation"]
            print(f"Node {self.node_id}: Handling Request: {request}")
            response = None

            if operation == "JOIN_NETWORK":
                response = self._handle_join_request(request)

            # Add more operations here as needed

            conn.sendall(pickle.dumps(response))  # Serialize and send the response
        except Exception as e:
            print(f"Error handling request: {e}")
        finally:
            conn.close()

    def send_request(self, node, request):
        """
        Send a request to a node and wait for its response.
        """
        # Use loopback IP for actual connection
        connect_address = ("127.0.0.1", node.address[1])

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # s.settimeout(10)  # Set a timeout for both connect and recv
            try:
                s.connect(connect_address)  # Connect using loopback
                s.sendall(pickle.dumps(request))  # Serialize and send the request
                response = s.recv(1024)  # Receive the response
            except Exception as e:
                print(f"Error connecting to {connect_address}: {e}")
                return None

        return pickle.loads(response)  # Deserialize the response

    # Node Joining and Routing

    def _handle_join_request(self, request):
        """
        Handle a request from a new node to join the network.
        """
        new_node_id = request["joining_node_id"]
        new_node = self.network.nodes[new_node_id]

        # Determine the routing table row to update
        i = common_prefix_length(self.node_id, new_node.node_id)

        # Update the new node's Routing Table row
        self.network.nodes[new_node.node_id].update_routing_table(
            i, self.routing_table[i]
        )

        self._forward_request(request)

        # Return a success response
        return {"status": "success"}

    def _forward_request(self, request):
        """
        Forward a request to the next node in the route.
        """
        operation = request["operation"]
        if operation == "JOIN_NETWORK":
            new_node_id = request["joining_node_id"]
            new_node = self.network.nodes[new_node_id]

            # Add the current node to the set of visited nodes
            visited_nodes = request["visited_nodes"]
            visited_nodes.add(self.node_id)  # Mark the current node as visited

            next_hop_id = self._find_next_hop(new_node.node_id)

            if next_hop_id == self.node_id:
                # If the next hop is the current node, update the new node's Leaf Set
                self.network.nodes[new_node.node_id].update_leaf_set(
                    self.Lmin, self.Lmax, self.node_id
                )
                return

            if next_hop_id in visited_nodes:
                return

            # Else forward the request to the next hop
            next_hop_node = self.network.nodes[next_hop_id]
            self.send_request(next_hop_node, request)

    def _find_next_hop(self, key):
        """
        Find the next hop to forward a request based on the node ID.
        """
        # Check if the key is in the leaf set
        if self._in_leaf_set(key):
            # If the node_id is in the leaf set
            closest_leaf_id = self._find_closest_leaf_id(key)
            return closest_leaf_id

        # If the key is not in the leaf set, check the routing table
        else:
            i = common_prefix_length(self.node_id, key)
            next_hop = self.routing_table[i][int(key[i], 16)]

            if next_hop is not None:
                return next_hop
            # If the routing table entry is empty,
            # scan all the nodes in the network
            else:
                next_hop = self._find_closest_node_id_all(key)
                return next_hop

    def transmit_state(self):
        """
        Broadcast the arrival of this node to the network.
        """
        node_id = self.node_id

        # Update the Neighborhood Set (M) nodes
        for i in range(len(self.neighborhood_set)):
            if self.neighborhood_set[i] is not None:
                self.network.nodes[self.neighborhood_set[i]]._update_presence(node_id)

        # Update the Routing Table (R) nodes
        for i in range(len(self.routing_table)):
            for j in range(len(self.routing_table[0])):
                if self.routing_table[i][j] is not None:
                    self.network.nodes[self.routing_table[i][j]]._update_presence(
                        node_id
                    )

        # Update the Leaf Set (L) Nodes

        # Iterate through the Lmin list
        for i in range(len(self.Lmin)):
            # Check if the current entry in the Lmin list is not None
            if self.Lmin[i] is not None:
                # Update the presence of the node in the network
                self.network.nodes[self.Lmin[i]]._update_presence(node_id)

        # Iterate through the Lmax list
        for i in range(len(self.Lmax)):
            # Check if the current entry in the Lmax list is not None
            if self.Lmax[i] is not None:
                # Update the presence of the node in the network
                self.network.nodes[self.Lmax[i]]._update_presence(node_id)

    # Data Structure Updates

    def update_routing_table(self, row_idx, received_row):
        """
        Update the routing table of the current node with the received row.
        """
        for col_idx in range(len(received_row)):
            entry = received_row[col_idx]
            if entry is None:
                continue
            # Skip if the entry's hex digit at row_idx matches this node's ID at the same index.
            # This avoids conflicts in the routing table.
            if entry[row_idx] == self.node_id[row_idx]:
                continue
            # Update the routing table with the received entry if the current entry is empty
            if self.routing_table[row_idx][col_idx] is None:
                self.routing_table[row_idx][col_idx] = received_row[col_idx]

    def initialize_neighborhood_set(self, close_node_id):
        """
        Initialize the neighborhood set of the current node using the close_node.
        """
        close_node = self.network.nodes[close_node_id]

        self.neighborhood_set = close_node.neighborhood_set.copy()

        # Insert the close node aswell if there is space
        for i in range(len(self.neighborhood_set)):
            if self.neighborhood_set[i] is None:
                self.neighborhood_set[i] = close_node.node_id
                return

        # If there is no space, replace the farthest node id with the close node
        max_dist = -1
        idx = -1
        for i in range(len(self.neighborhood_set)):
            dist = topological_distance(self.address[0], close_node.address[0])
            if dist > max_dist:
                max_dist = dist
                idx = i
        self.neighborhood_set[idx] = close_node.node_id

    def _update_neighborhood_set(self, key):
        """
        Update the neighborhood set of the current node by adding a new key if there's space
        or replacing the farthest node if necessary.
        """
        # Check for an empty slot in the neighborhood set
        for i, neighbor in enumerate(self.neighborhood_set):
            if neighbor is None:
                self.neighborhood_set[i] = key  # Add the key to the empty slot
                return

        # Initialize variables to find the farthest node in the neighborhood set
        max_dist, replace_idx = -1, -1

        # Find the farthest node from the current node in the neighborhood set
        for i, neighbor_id in enumerate(self.neighborhood_set):
            dist = topological_distance(
                self.network.nodes[neighbor_id].address[0], self.address[0]
            )
            if dist > max_dist:
                max_dist, replace_idx = dist, i

        # Check if the new node is closer than the farthest node
        key_farthest_dist = topological_distance(
            self.network.nodes[self.neighborhood_set[replace_idx]].address[0],
            self.network.nodes[key].address[0],
        )
        if key_farthest_dist < max_dist:
            # Replace the farthest node with the new node
            self.neighborhood_set[replace_idx] = key

    def update_leaf_set(self, Lmin, Lmax, key):
        """
        Update the leaf set of the current node based on the provided Lmin, Lmax,
        and key of the node that triggered the update.
        """
        self.Lmin = Lmin.copy()
        self.Lmax = Lmax.copy()

        if hex_compare(key, self.node_id):
            # If key >= this node's ID, update Lmax
            self._update_leaf_list(self.Lmax, key)
        else:
            # Else update Lmin
            self._update_leaf_list(self.Lmin, key)

    def _update_presence(self, key):
        """
        Update the presence of a node in all the data structures of this node.
        """
        # Neighborhood Set (M)
        if key not in self.neighborhood_set:
            self._update_neighborhood_set(key)

        # Routing Table (R)
        # Find the length of the common prefix between the key and the current node's ID
        idx = common_prefix_length(key, self.node_id)

        # If the entry in the routing table is empty, update it with the key
        if self.routing_table[idx][int(key[idx], 16)] is None:
            self.routing_table[idx][int(key[idx], 16)] = key

        """Giati to ekana auto!! na to psaksw an xreiazetai"""
        # If the entry in the routing table of the node corresponding to the key
        # is empty, update it with the current node's ID
        if (
            self.network.nodes[key].routing_table[idx][int(self.node_id[idx], 16)]
            is None
        ):
            self.network.nodes[key].routing_table[idx][
                int(self.node_id[idx], 16)
            ] = self.node_id

        # Leaf Set (Lmin, Lmax)
        # If key >= this node's ID, update Lmax
        if hex_compare(key, self.node_id):
            if key not in self.Lmax:
                self._update_leaf_list(self.Lmax, key)
        # Else update Lmin
        else:
            if key not in self.Lmin:
                self._update_leaf_list(self.Lmin, key)

    # Helper Methods

    def _in_leaf_set(self, node_id):
        """
        Check if a node ID is in the leaf set.
        """
        if node_id in self.Lmin or node_id in self.Lmax:
            return True
        else:
            return False

    def _find_closest_leaf_id(self, key):
        closest_diff_dig_idx, closest_dist = hex_distance(self.node_id, key)

        closest_leaf_id = self.node_id

        # Check Lmin for closer nodes
        for leaf in self.Lmin:
            if leaf is not None:
                key_leaf_diff_dig_idx, key_leaf_dist = hex_distance(leaf, key)

                # Update if the different digit index is grater
                # or if its the same but this node is numerically closer
                if (key_leaf_diff_dig_idx > closest_diff_dig_idx) or (
                    key_leaf_diff_dig_idx == closest_diff_dig_idx
                    and key_leaf_dist < closest_dist
                ):
                    closest_leaf_id = leaf
                    closest_diff_dig_idx = key_leaf_diff_dig_idx
                    closest_dist = key_leaf_dist

        # Check Lmax for closer nodes
        for leaf in self.Lmax:
            if leaf is not None:
                key_leaf_diff_dig_idx, key_leaf_dist = hex_distance(leaf, key)

                # Apply the same update logic
                if (key_leaf_diff_dig_idx > closest_diff_dig_idx) or (
                    key_leaf_diff_dig_idx == closest_diff_dig_idx
                    and key_leaf_dist < closest_dist
                ):
                    closest_leaf_id = leaf
                    closest_diff_dig_idx = key_leaf_diff_dig_idx
                    closest_dist = key_leaf_dist

        return closest_leaf_id

    def _find_closest_node_id_all(self, key):
        """
        Scan all the nodes in the network to find the closest node to the given node ID.
        """
        i = common_prefix_length(self.node_id, key)

        # Check Lmin
        for idx in range(len(self.Lmin)):
            if self.Lmin[idx] is not None:
                if self._is_closer_node(self.Lmin[idx], key, idx, self.node_id):
                    return self.Lmin[idx]

        # Check Lmax
        for idx in range(len(self.Lmax)):
            if self.Lmax[idx] is not None:
                if self._is_closer_node(self.Lmax[idx], key, idx, self.node_id):
                    return self.Lmax[idx]

        # Check neighborhood set (M)
        for idx in range(len(self.neighborhood_set)):
            if self.neighborhood_set[idx] is not None:
                if self._is_closer_node(
                    self.neighborhood_set[idx], key, idx, self.node_id
                ):
                    return self.neighborhood_set[idx]

        # Check routing table (R)
        for row in range(len(self.routing_table)):
            for col in range(len(self.routing_table[0])):
                if self.routing_table[row][col] is not None:
                    if self._is_closer_node(
                        self.routing_table[row][col], key, row, self.node_id
                    ):
                        return self.routing_table[row][col]

        # If no node is found, return the current node ID
        return self.node_id

    def _is_closer_node(self, target_node_id, key, l, curr_node_id):
        """
        Custom condition to compare the target and current nodes based on topological and numerical closeness to the key.
        """
        # Calculate the common prefix length between the target node and the key
        i = common_prefix_length(target_node_id, key)

        # Calculate the first different digit index between the target node id and the key
        # and the numerical distance between the target node and the key
        target_key_diff_dig_idx, target_key_num_dist = hex_distance(target_node_id, key)

        # Do the same for the current node and the key
        curr_node_key_diff_dig_idx, curr_node_key_num_dist = hex_distance(
            curr_node_id, key
        )

        # Determine if the target node is a better candidate than the current node
        if (i >= l) and (
            (target_key_diff_dig_idx > curr_node_key_diff_dig_idx)
            or (
                target_key_diff_dig_idx == curr_node_key_diff_dig_idx
                and target_key_num_dist < curr_node_key_num_dist
            )
        ):
            return True
        else:
            return False

    def _update_leaf_list(self, leaf_list, key):
        """
        Update the specified leaf list (Lmin or Lmax) with the given key.
        """
        # Iterate through the leaf list to find an empty slot
        for i in range(len(leaf_list)):
            if leaf_list[i] is None:
                leaf_list[i] = key
                return

        # If there are no empty slots, find the farthest node
        far_diff_dig_idx = HASH_HEX_DIGITS
        max_num_dist = -1
        replace_index = -1

        # Iterate through the Lmax list to find the numerically farthest node
        for i in range(len(leaf_list)):
            diff_dig_idx, num_dist = hex_distance(leaf_list[i], self.node_id)

            # Update the max_dist and replace_index if a smaller different digit index
            # or a larger distance is found
            if (diff_dig_idx < far_diff_dig_idx) or (
                diff_dig_idx == far_diff_dig_idx and num_dist > max_num_dist
            ):
                far_diff_dig_idx = diff_dig_idx
                max_num_dist = num_dist
                replace_index = i

        # Calculate the numerical distance for the new key
        diff_dig_idx, num_dist = hex_distance(key, self.node_id)

        # If the new key is closer than the current farthest node, replace it
        if (diff_dig_idx > far_diff_dig_idx) or (
            diff_dig_idx == far_diff_dig_idx and num_dist < max_num_dist
        ):
            leaf_list[replace_index] = key
