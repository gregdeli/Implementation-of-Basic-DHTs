import threading
import socket
import pickle
from concurrent.futures import ThreadPoolExecutor
import numpy as np

import sys
import os

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from constants import *
from helper_functions import *


from Multidimensional_Data_Structures.kd_tree import KDTree
from Multidimensional_Data_Structures.lsh import LSH
from sklearn.feature_extraction.text import TfidfVectorizer


class PastryNode:

    def __init__(self, network, node_id=None):
        """
        Initialize a new Pastry node with a unique ID, Port, Position, and empty data structures.
        """
        self.network = network  # Reference to the DHT network
        self.port = self._generate_port()  # IP = (127.0.0.1, Port)

        self.node_id = node_id if node_id is not None else self._generate_id(self.port)
        self.position = None  # Position will be generated by the network
        self.kd_tree = None  # Centralized KD-Tree object

        # 2D Routing Table
        self.routing_table = [[None for j in range(pow(2, b))] for i in range(HASH_HEX_DIGITS)]
        # Leaf Set

        self.Lmin = [None for x in range(L // 2)]
        self.Lmax = [None for x in range(L // 2)]
        # Nearby nodes

        self.neighborhood_set = [None for x in range(np.floor(np.sqrt(N)).astype(int))]

        self.lock = threading.Lock()  # Lock for thread safety

        # Create a thread pool for handling requests to limit the number of concurrent threads
        self.thread_pool = ThreadPoolExecutor(max_workers=10)

    # Initialization Methods

    def _generate_port(self, port=None):
        """
        Generate a unique address Port for the node.
        """
        port = port or np.random.randint(1024, 65535)  # Random port if not provided

        # If the port is already in use, generate a new one
        while port in self.network.used_ports:
            port = np.random.randint(1024, 65535)
        self.network.used_ports.append(port)
        return port

    def _generate_id(self, port):
        """
        Generate a unique node ID by hashing the port.
        """
        port_str = f"{port}"
        node_id = hash_key(port_str)
        return node_id

    # State Inspection

    def print_state(self):
        """
        Print the state of the node (ID, Port, Position, Data Structures).
        """
        print("\n" + "-" * 100)
        print(f"Node ID: {self.node_id}")
        print(f"Port: {self.port}")
        print(f"Position: {self.position}")
        print("\nRouting Table:")
        for row in self.routing_table:
            print(row)
        print("\nLeaf Set:")
        print(f"Lmin: {self.Lmin}")
        print(f"Lmax: {self.Lmax}")
        print("\nNeighborhood Set:")
        print(self.neighborhood_set)
        print("\nKD Tree Coutry Keys:")
        if self.kd_tree:
            # Print the unique country keys in the KD-Tree
            print(np.unique(self.kd_tree.country_keys))
        else:
            print([])

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
        bind_address = (bind_ip, self.port)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(bind_address)  # Bind to localhost
            except OSError as e:
                print(f"Error binding to {bind_address}: {e}")
                return

            s.listen()
            print(f"Node {self.node_id} listening on {bind_address})")
            while True:
                conn, addr = s.accept()  # Accept incoming connection
                # Submit the connection to the thread pool for handling
                self.thread_pool.submit(self._handle_request, conn)

    def _handle_request(self, conn):
        try:
            data = conn.recv(1024)  # Read up to 1024 bytes of data
            request = pickle.loads(data)  # Deserialize the request
            operation = request["operation"]
            hops = request.get("hops", [])
            hops.append(self.node_id)  # Add the current node to the hops list

            print(f"Node {self.node_id}: Handling Request: {request}")
            response = None

            if operation == "NODE_JOIN":
                response = self._handle_join_request(request)
            elif operation == "NODE_LEAVE":
                response = self._handle_leave_request(request)
            elif operation == "INSERT_KEY":
                response = self._handle_insert_key_request(request)
            elif operation == "UPDATE_KEY":
                response = self._handle_update_key_request(request)
            elif operation == "DELETE_KEY":
                response = self._handle_delete_key_request(request)
            elif operation == "LOOKUP":
                response = self._handle_lookup_request(request)
            elif operation == "UPDATE_PRESENCE":
                response = self._handle_update_presence_request(request)
            elif operation == "UPDATE_ROUTING_TABLE_ROW":
                response = self.update_routing_table_row(request)
            elif operation == "UPDATE_ROUTING_TABLE_ENTRY":
                response = self.update_routing_table_entry(request)
            elif operation == "UPDATE_LEAF_SET":
                response = self.update_leaf_set(request)
            elif operation == "DISTANCE":
                distance = topological_distance(self.position, request["node_position"])
                response = {"distance": distance, "neighborhood_set": self.neighborhood_set}
            elif operation == "GET_LEAF_SET":
                response = {
                    "status": "success",
                    "leaf_set": {"Lmin": self.Lmin, "Lmax": self.Lmax},
                }
            else:
                response = {"status": "failure", "message": "Unknown operation"}

            # Add more operations here as needed

            conn.sendall(pickle.dumps(response))  # Serialize and send the response
        except Exception as e:
            print(f"Error handling request: {e}")
        finally:
            conn.close()

    def send_request(self, node_port, request):
        """
        Send a request to a node and wait for its response.
        """
        # Use loopback IP for actual connection
        connect_address = ("127.0.0.1", node_port)

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

        # Determine the routing table row to update
        i = common_prefix_length(self.node_id, new_node_id)

        # Update the new node's Routing Table row
        update_R_request = {
            "operation": "UPDATE_ROUTING_TABLE_ROW",
            "row_idx": i,
            "received_row": self.routing_table[i],
            "hops": [],
        }
        print(
            f"Node {self.node_id}: Updating the new node's Routing Table Row {i} with node's {self.node_id} row {i}..."
        )
        self.send_request(self.network.node_ports[new_node_id], update_R_request)

        next_hop_id = self._find_next_hop(new_node_id)

        if next_hop_id == self.node_id:
            # If the next hop is the current node, update the new node's Leaf Set
            print(
                f"Node {self.node_id}: This node is the numerically closest node to the new node.\nUpdating the new node's Leaf Set..."
            )
            update_L_request = {
                "operation": "UPDATE_LEAF_SET",
                "Lmin": self.Lmin,
                "Lmax": self.Lmax,
                "key": self.node_id,
                "hops": [],
            }
            self.send_request(self.network.node_ports[new_node_id], update_L_request)

            return {
                "status": "success",
            }

        # Else forward the request to the next hop
        response = self.send_request(self.network.node_ports[next_hop_id], request)
        return response

    def _handle_insert_key_request(self, request):
        """
        Handle an INSERT_KEY operation.
        """
        key = request["key"]
        point = request["point"]
        review = request["review"]
        country = request["country"]
        country_key = hash_key(country)
        hops = request.get("hops", [])

        next_hop_id = self._find_next_hop(key)

        # Determine if this node should store the key or forward it
        if self._in_leaf_set(key) or next_hop_id == self.node_id:
            if not self.kd_tree:
                # Initialize KDTree with the first point
                self.kd_tree = KDTree(
                    points=np.array([point]),
                    reviews=np.array([review]),
                    country_keys=np.array([country_key]),
                )
            else:
                # Add point to the existing KDTree
                self.kd_tree.add_point(point, review, country)

            # Print the point and review directly after adding
            print(f"\nInserted Key: {key}")
            print(f"Point: {point}")
            print(f"Review: {review}")
            print(f"Routed and stored at Node ID: {self.node_id}")
            print(f"Hops: {hops}")
            print("")
            return {
                "status": "success",
                "message": f"Key {key} stored at {self.node_id}",
            }

        # If this node is not responsible for the key forward request to the next hop
        return self.send_request(self.network.node_ports[next_hop_id], request)

    def _handle_delete_key_request(self, request):
        """
        Handle a DELETE_KEY operation.
        """
        key = request["key"]

        next_hop_id = self._find_next_hop(key)

        # If the key belongs to this node (based on leaf set), delete it from the KDTree
        if self._in_leaf_set(key) or next_hop_id == self.node_id:
            if not self.kd_tree:
                print(f"\nNode {self.node_id}: No data for key {key}.")
                return {"status": "failure", "message": f"No data for key {key}.\n"}

            # Delete the key from the KDTree if it exists
            if key in self.kd_tree.country_keys:
                print(f"\nNode {self.node_id}: Deleted Key {key}.")
                self.kd_tree.delete_points(key)
            else:
                print(f"\nNode {self.node_id}: No data for key {key}.\n")
                return {"status": "failure", "message": f"No data for key {key}."}

            return {"status": "success", "message": f"Deleted Key {key}."}

        # Otherwise, forward the request to the next node
        response = self.send_request(self.network.node_ports[next_hop_id], request)
        return response

    def _handle_lookup_request(self, request):
        """
        Handle a LOOKUP operation.
        """
        key = request["key"]
        lower_bounds = request["lower_bounds"]
        upper_bounds = request["upper_bounds"]
        N = request["N"]

        # If this key is found in the leaf set or the next hop is the current node the lookup is successful
        next_hop_id = self._find_next_hop(key)

        if self._in_leaf_set(key) or next_hop_id == self.node_id:
            print(f"\nNode {self.node_id}: Lookup Key {key} Found.")

            # If the KDTree is not initialized or has no data, return a failure message
            if not self.kd_tree or self.kd_tree.points.size == 0:
                print(f"Node {self.node_id}: No data for key {key}.")
                return {"status": "failure", "message": f"No data for key {key}."}

            # KDTree Range Search
            points, reviews = self.kd_tree.search(lower_bounds, upper_bounds)
            print(f"Node {self.node_id}: Found {len(points)} matching points.")

            # LSH Similarity Search
            vectorizer = TfidfVectorizer()
            doc_vectors = vectorizer.fit_transform(reviews).toarray()

            lsh = LSH(num_bands=4, num_rows=5)
            for vector in doc_vectors:
                lsh.add_document(vector)

            similar_pairs = lsh.find_similar_pairs(N)
            similar_docs = lsh.find_similar_docs(similar_pairs, reviews, N)

            print(f"\nThe {N} Most Similar Reviews:\n")
            for i, doc in enumerate(similar_docs, 1):
                print(f"{i}. {doc}\n")

            return {
                "status": "success",
                "message": f"Found {len(points)} matching points.",
            }

        # If the key is not found in the leaf set and the next hop is not the current node
        # forward the request to the next hop
        response = self.send_request(self.network.node_ports[next_hop_id], request)
        return response

    def _handle_update_key_request(self, request):
        """
        Handle an UPDATE_KEY operation with criteria and update fields.
        """
        key = request["key"]
        criteria = request.get("criteria", None)  # Optional criteria to filter
        update_fields = request["data"]  # Update fields for the KDTree
        hops = request.get("hops", [])

        # Add current node to hops
        hops.append(self.node_id)

        # Find the next hop or check if this node is responsible for the key
        next_hop_id = self._find_next_hop(key)

        if self._in_leaf_set(key) or next_hop_id == self.node_id:
            # Check if the key exists in this node's data structure
            if self.kd_tree and key in self.kd_tree.country_keys:
                # Update the data in the KDTree
                self.kd_tree.update_points(
                    country_key=key,
                    criteria=criteria,
                    update_fields=update_fields,
                )
                print(f"Node {self.node_id}: Key {key} updated successfully.")
                return {
                    "status": "success",
                    "message": f"Key {key} updated successfully.",
                    "hops": hops,
                }
            else:
                return {"status": "failure", "message": f"Key {key} not found.", "hops": hops}

        # Forward the request to the next hop if not responsible for the key
        return self.send_request(self.network.node_ports[next_hop_id], request)

    def _repair_leaf_set(self):
        for leaf in self.Lmin + self.Lmax:
            if leaf and leaf != self.node_id:
                try:
                    request = {"operation": "GET_LEAF_SET"}
                    response = self.send_request(self.network.node_ports[leaf], request)
                    if response["status"] == "success":
                        for new_leaf in response["leaf_set"]["Lmin"] + response["leaf_set"]["Lmax"]:
                            if (
                                new_leaf
                                and new_leaf != self.node_id
                                and new_leaf not in self.Lmin + self.Lmax
                            ):
                                self._update_leaf_list(self.Lmin, new_leaf)
                                self._update_leaf_list(self.Lmax, new_leaf)
                except Exception as e:
                    print(f"Error repairing leaf set with node {leaf}: {e}")

    def _handle_leave_request(self, request):
        leaving_node_id = request["leaving_node_id"]
        print(f"Node {self.node_id}: Handling NODE_LEAVE for {leaving_node_id}.")

        # Remove the leaving node from the network
        with self.lock:
            if leaving_node_id in self.network.nodes:
                del self.network.nodes[leaving_node_id]

        # Identify all nodes that are affected by the departure
        affected_nodes = []
        for node_id, node in self.network.nodes.items():
            if (
                leaving_node_id in node.Lmin
                or leaving_node_id in node.Lmax
                or leaving_node_id in node.neighborhood_set
                or any(
                    leaving_node_id == entry
                    for row in node.routing_table
                    for entry in row
                    if entry is not None
                )
            ):
                affected_nodes.append(node_id)

        # Rebuild the state for all affected nodes
        for node_id in affected_nodes:
            node = self.network.nodes[node_id]
            node._rebuild_node_state()

        print(f"Node {self.node_id}: Updated network after {leaving_node_id} left.")
        return {"status": "success", "message": f"Processed NODE_LEAVE for {leaving_node_id}."}

    def _rebuild_node_state(self):
        """
        Rebuild the Lmin, Lmax, neighborhood_set, and routing_table of this node.
        """
        print(f"Node {self.node_id}: Rebuilding state.")

        # Get all available nodes in the network except self
        available_nodes = [node_id for node_id in self.network.nodes if node_id != self.node_id]

        # Rebuild Lmin and Lmax
        self.Lmin = self._find_closest_lower_nodes(available_nodes)
        self.Lmax = self._find_closest_higher_nodes(available_nodes)

        # Rebuild neighborhood_set
        self.neighborhood_set = self._update_closest_neighbors()

        # Rebuild routing_table
        self.routing_table = [[None for _ in range(pow(2, b))] for _ in range(HASH_HEX_DIGITS)]
        for node_id in available_nodes:
            common_prefix = common_prefix_length(self.node_id, node_id)
            col = int(node_id[common_prefix], 16)
            if self.routing_table[common_prefix][col] is None:
                self.routing_table[common_prefix][col] = node_id

        print(f"Node {self.node_id}: Rebuilding complete.")

    def _find_closest_lower_nodes(self, available_nodes):
        """
        Find the closest numerically smaller nodes to populate Lmin.
        """
        # Filter nodes that are numerically smaller than the current node
        lower_nodes = [n for n in available_nodes if n < self.node_id]

        # Compute distances for debugging
        distances = {n: int(self.node_id, 16) - int(n, 16) for n in lower_nodes}

        # Sort nodes by distance
        lower_nodes.sort(key=lambda n: distances[n])

        # Ensure Lmin has exactly L // 2 nodes (fill with None if not enough nodes)
        result = lower_nodes[: L // 2] + [None] * (L // 2 - len(lower_nodes))

        return result

    def _find_closest_higher_nodes(self, available_nodes):
        """
        Find the closest numerically higher nodes to populate Lmax.
        """
        print(f"\nNode {self.node_id}: Finding closest numerically higher nodes.")
        print(f"Available nodes: {available_nodes}")

        # Filter nodes that are numerically higher than the current node
        higher_nodes = [n for n in available_nodes if n > self.node_id]

        # Compute distances for debugging
        distances = {n: int(n, 16) - int(self.node_id, 16) for n in higher_nodes}

        # Sort nodes by distance
        higher_nodes.sort(key=lambda n: distances[n])

        # Ensure Lmax has exactly L // 2 nodes (fill with None if not enough nodes)
        result = higher_nodes[: L // 2] + [None] * (L // 2 - len(higher_nodes))
        return result

    def _update_closest_neighbors(self):
        """
        Update the neighborhood set with the closest nodes by position.
        """
        available_nodes = [n for n in self.network.nodes if n != self.node_id]
        available_nodes.sort(key=lambda n: abs(self.position - self.network.nodes[n].position))

        # Return the 3 closest nodes
        return available_nodes[:3]

    def insert_key(self, key, point, review, country):
        """
        Initiate the INSERT_KEY operation for a given key, point, and review.
        """
        request = {
            "operation": "INSERT_KEY",
            "key": key,
            "country": country,
            "point": point,
            "review": review,
            "hops": [],  # Initialize hops tracking
        }
        print(f"Node {self.node_id}: Handling Request: {request}")

        response = self._handle_insert_key_request(request)
        return response

    def delete_key(self, key):
        """
        Delete a key from the network.
        """
        request = {
            "operation": "DELETE_KEY",
            "key": key,
            "hops": [],
        }
        print(f"Node {self.node_id}: Handling Request: {request}")
        response = self._handle_delete_key_request(request)
        return response

    def lookup(self, key, lower_bounds, upper_bounds, N=5):
        """
        Lookup operation for a given key with KDTree range search and LSH similarity check.
        """
        request = {
            "operation": "LOOKUP",
            "key": key,
            "lower_bounds": lower_bounds,
            "upper_bounds": upper_bounds,
            "N": N,
            "hops": [],
        }
        print(f"Node {self.node_id}: Handling Request: {request}")

        response = self._handle_lookup_request(request)
        return response

    def update_key(self, key, updated_data, criteria=None):
        """
        Initiate the UPDATE_KEY operation for a given key with optional criteria and updated data.

        Args:
            key (str): The key (hashed country) to be updated.
            updated_data (dict): Fields to update. Example: {"attributes": {"price": 30.0}, "review": "Updated review"}.
            criteria (dict, optional): Criteria for selecting points to update.
                                    Example: {"review_date": 2019, "rating": 94}.

        Returns:
            dict: Response from the update operation, indicating success or failure.
        """
        request = {
            "operation": "UPDATE_KEY",
            "key": key,
            "data": updated_data,
            "criteria": criteria,  # Optional criteria for filtering
            "hops": [],  # Initialize hops tracking
        }
        print(f"Node {self.node_id}: Handling Update Request: {request}")
        response = self._handle_update_key_request(request)
        return response

    def leave(self):
        print(f"Node {self.node_id} is leaving the network...")

        # Identify affected nodes
        affected_nodes = set(self.Lmin + self.Lmax + self.neighborhood_set)
        for row in self.routing_table:
            affected_nodes.update(filter(None, row))

        # Notify affected nodes
        for node_id in affected_nodes:
            if node_id and node_id != self.node_id:
                leave_request = {
                    "operation": "NODE_LEAVE",
                    "leaving_node_id": self.node_id,
                }
                target_node = self.network.nodes.get(node_id)
                if target_node:
                    self.send_request(target_node, leave_request)

        # Safely remove the node from the network
        with self.lock:
            if self.node_id in self.network.nodes:
                del self.network.nodes[self.node_id]
                print(f"Node {self.node_id} has been removed from the network.")
            else:
                print(f"Node {self.node_id} is not found in the network.")

        # Rebuild state for affected nodes
        for node_id in affected_nodes:
            if node_id in self.network.nodes:
                self.network.nodes[node_id]._rebuild_node_state()

        print(f"Node {self.node_id} has successfully left the network.")

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
        Broadcast the arrival of this node to the network, ensuring each node is updated only once.
        """
        request = {
            "operation": "UPDATE_PRESENCE",
            "joining_node_id": self.node_id,
            "hops": [],
        }

        nodes_updated = set()

        def __update_presence(node_id):
            """Helper function to send request and track updates."""
            if node_id is not None and node_id not in nodes_updated:
                self.send_request(self.network.node_ports[node_id], request)
                nodes_updated.add(node_id)

        # Update the Neighborhood Set (M) nodes
        for node_id in self.neighborhood_set:
            __update_presence(node_id)

        # Update the Routing Table (R) nodes
        for row in self.routing_table:
            for node_id in row:
                __update_presence(node_id)

        # Update the Leaf Set (L) nodes
        for node_id in self.Lmin:
            __update_presence(node_id)

        for node_id in self.Lmax:
            __update_presence(node_id)

    # Data Structure Updates

    def update_routing_table_row(self, request):
        """
        Update the routing table of the current node with the received row.
        """
        row_idx = request["row_idx"]
        received_row = request["received_row"]

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

    def update_routing_table_entry(self, request):
        """
        Update a single entry in the routing table of the current node.
        """
        idx = request["row_idx"]
        node_id = request["node_id"]

        # Update the routing table entry if it is empty
        if self.routing_table[idx][int(node_id[idx], 16)] is None:
            print(f"Node {self.node_id}: Updating Routing Table Entry for new node {node_id}...")
            self.routing_table[idx][int(node_id[idx], 16)] = node_id

    def initialize_neighborhood_set(self, close_node_id, close_node_neighborhood_set):
        """
        Initialize the neighborhood set of the current node using the close_node.
        """

        self.neighborhood_set = close_node_neighborhood_set
        print(
            f"Node {self.node_id}: Copying neighborhood set from the closest node {close_node_id}..."
        )

        # Insert the close node aswell if there is space
        print(
            f"Node {self.node_id}: Adding Node close node {close_node_id} to the neighborhood set aswell..."
        )
        for i in range(len(self.neighborhood_set)):
            if self.neighborhood_set[i] is None:
                self.neighborhood_set[i] = close_node_id
                return

        # If there is no space, replace the farthest node id with the close node
        print(
            f"Node {self.node_id}: No space in the neighborhood set for the close node. Replacing the farthest node..."
        )
        max_dist = -1
        idx = -1
        for i in range(len(self.neighborhood_set)):
            dist_request = {
                "operation": "DISTANCE",
                "node_position": self.position,
                "hops": [],
            }
            response = self.send_request(
                self.network.node_ports[self.neighborhood_set[i]], dist_request
            )
            dist = response["distance"]

            if dist > max_dist:
                max_dist = dist
                idx = i
        self.neighborhood_set[idx] = close_node_id

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
            dist = topological_distance(self.network.nodes[neighbor_id].position, self.position)
            if dist > max_dist:
                max_dist, replace_idx = dist, i

        # Check if the new node is closer than the farthest node
        key_curr_node_dist = topological_distance(
            self.position,
            self.network.nodes[key].position,
        )
        if key_curr_node_dist < max_dist:
            # Replace the farthest node with the new node
            self.neighborhood_set[replace_idx] = key

    def update_leaf_set(self, request):
        """
        Update the leaf set of the current node based on the provided Lmin, Lmax,
        and key of the node that triggered the update.
        """
        Lmin = request["Lmin"]
        Lmax = request["Lmax"]
        key = request["key"]

        self.Lmin = Lmin.copy()
        self.Lmax = Lmax.copy()

        if hex_compare(key, self.node_id):
            # If key >= this node's ID, update Lmax
            self._update_leaf_list(self.Lmax, key)
        else:
            # Else update Lmin
            self._update_leaf_list(self.Lmin, key)

    def _handle_update_presence_request(self, request):
        """
        Update the presence of a node in all the data structures of this node.
        """
        key = request["joining_node_id"]

        # Neighborhood Set (M)
        if key not in self.neighborhood_set:
            self._update_neighborhood_set(key)

        # Routing Table (R)
        # Find the length of the common prefix between the key and the current node's ID
        idx = common_prefix_length(key, self.node_id)

        # If the entry in the routing table is empty, update it with the key
        print(f"Node {self.node_id}: Updating Routing Table Entry for new node {key}...")
        if self.routing_table[idx][int(key[idx], 16)] is None:
            self.routing_table[idx][int(key[idx], 16)] = key

        # Also update the new node's routing table with the current node's id
        request = {
            "operation": "UPDATE_ROUTING_TABLE_ENTRY",
            "row_idx": idx,
            "node_id": self.node_id,
            "hops": [],
        }
        self.send_request(self.network.node_ports[key], request)

        # Leaf Set (Lmin, Lmax)
        print(f"Node {self.node_id}: Updating Leaf Set for new node {key}...")
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
                    key_leaf_diff_dig_idx == closest_diff_dig_idx and key_leaf_dist < closest_dist
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
                    key_leaf_diff_dig_idx == closest_diff_dig_idx and key_leaf_dist < closest_dist
                ):
                    closest_leaf_id = leaf
                    closest_diff_dig_idx = key_leaf_diff_dig_idx
                    closest_dist = key_leaf_dist

        return closest_leaf_id

    def _find_closest_node_id_all(self, key):
        """
        Scan all the nodes in the network to find the closest node to the given node ID.
        """
        l = common_prefix_length(self.node_id, key)

        # Check Lmin
        for idx in range(len(self.Lmin)):
            if self.Lmin[idx] is not None:
                if self._is_closer_node(self.Lmin[idx], key, l, self.node_id):
                    return self.Lmin[idx]

        # Check Lmax
        for idx in range(len(self.Lmax)):
            if self.Lmax[idx] is not None:
                if self._is_closer_node(self.Lmax[idx], key, l, self.node_id):
                    return self.Lmax[idx]

        # Check neighborhood set (M)
        for idx in range(len(self.neighborhood_set)):
            if self.neighborhood_set[idx] is not None:
                if self._is_closer_node(self.neighborhood_set[idx], key, l, self.node_id):
                    return self.neighborhood_set[idx]

        # Check routing table (R)
        for row in range(len(self.routing_table)):
            for col in range(len(self.routing_table[0])):
                if self.routing_table[row][col] is not None:
                    if self._is_closer_node(self.routing_table[row][col], key, l, self.node_id):
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
        curr_node_key_diff_dig_idx, curr_node_key_num_dist = hex_distance(curr_node_id, key)

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
        Update the specified leaf list (Lmin or Lmax) with the given key, ensuring no duplicates.
        """
        # Ensure the key is not already in the combined leaf set
        if key in self.Lmin + self.Lmax:
            return

        # Find an empty slot in the leaf list
        for i in range(len(leaf_list)):
            if leaf_list[i] is None:
                leaf_list[i] = key
                return

        # If no empty slot, find the farthest node and replace it if the key is closer
        far_diff_dig_idx = HASH_HEX_DIGITS
        max_num_dist = -1
        replace_index = -1

        for i in range(len(leaf_list)):
            diff_dig_idx, num_dist = hex_distance(leaf_list[i], self.node_id)

            # Replace the farthest node (numerical distance or digit index)
            if (diff_dig_idx < far_diff_dig_idx) or (
                diff_dig_idx == far_diff_dig_idx and num_dist > max_num_dist
            ):
                far_diff_dig_idx = diff_dig_idx
                max_num_dist = num_dist
                replace_index = i

        # Calculate the numerical distance for the new key
        diff_dig_idx, num_dist = hex_distance(key, self.node_id)

        # Replace if the key is closer than the farthest node
        if (diff_dig_idx > far_diff_dig_idx) or (
            diff_dig_idx == far_diff_dig_idx and num_dist < max_num_dist
        ):
            leaf_list[replace_index] = key
