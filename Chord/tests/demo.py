import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import time

import threading

import pandas as pd

from Chord.network import ChordNetwork
from Chord.node import ChordNode
from constants import *
from helper_functions import *


def insert_keys(network, keys, points, reviews, countries, names):
    """Insert all keys sequentially."""
    responses = []
    for key, point, review, country, name in zip(keys, points, reviews, countries, names):
        # print(f"\nInserting Key: {key}, Country: {country}, Name: {name}\n")
        response = network.insert_key(key, point, review, country)
        responses.append(response["hops"])
    return responses


def delete_keys(network, keys):
    """Insert all keys sequentially."""
    responses = []
    for key in keys:
        response = network.delete_key(key)
        responses.append(response["hops"])
    return responses


def update_keys(network, keys):
    """Update all keys sequentially."""
    updated_data = {
        "point": [2018, 94, 5.5],
        "review": "New review text",
        "attributes": {"rating": 95},
    }
    hops = 0
    for key in keys:
        hops += network.update_key(key, updated_data)["hops"]
    return hops / len(keys)


def lookups(network, keys):
    """Perform lookups for all keys."""
    N = 3
    lower_bounds = [2018, 0, 0]
    upper_bounds = [2018, 100, 100]
    hops = 0
    for key in keys:
        hops += network.lookup(key, lower_bounds, upper_bounds, N)["hops"]
    return hops / len(keys)


def insert_key(network, key, point, review, country, name):
    """Insert a key."""
    # print(f"\nInserting Key: {key}, Country: {country}, Name: {name}\n")
    return network.insert_key(key, point, review, country)


def main():
    # Load dataset
    dataset_path = "../../Coffee_Reviews_Dataset/simplified_coffee.csv"
    df = pd.read_csv(dataset_path)

    # Keep only the year from the review_date column
    df["review_date"] = pd.to_datetime(df["review_date"], format="%B %Y").dt.year

    # Extract loc_country as keys
    keys = df["loc_country"].apply(hash_key)
    unique_keys = list(set(keys))

    # Extract data points (review_date, rating, 100g_USD)
    points = df[["review_date", "rating", "100g_USD"]].to_numpy()

    # Extract reviews and other details
    reviews = df["review"].to_numpy()
    countries = df["loc_country"].to_numpy()
    names = df["name"].to_numpy()

    # Create the Chord network
    print("Creating the Chord network...")
    network = ChordNetwork()

    ################################################################
    #                         NODES JOIN                           #
    ################################################################

    print(
        """\n################################################################
#                         NODES JOIN                           #
################################################################\n"""
    )

    print(f"Adding {len(predefined_ids)} nodes to the network...")

    hops = []
    # Node Insertion
    for node_id in predefined_ids:
        node = ChordNode(network, node_id=node_id)
        node.start_server()
        hops.append(len(network.node_join(node)) - 1)

    print(f"Num of hops to insert {len(hops)} nodes: {sum(hops)}")
    print(f"Avarage num of hops to insert a node: {sum(hops)/len(hops)}")
    ################################################################
    #                        KEYS INSERTION                        #
    ################################################################
    print(
        """\n################################################################
#                        KEYS INSERTION                        #
################################################################\n"""
    )
    print("\n" + "-" * 100 + "\n")
    print("-> Inserting Keys from Dataset...")
    insert_keys(network, keys, points, reviews, countries, names)
    print("-> End of Insertion")
    print("\n" + "-" * 100 + "\n")
    ################################################################
    #                        DEMOSTRATION                          #
    ################################################################
    print(
        """\n################################################################
#                        INSERT KEY                            #
################################################################\n"""
    )
    country = "Romania "
    name = "Carpathian Coffee"
    key = hash_key(country)
    point = [2023, 97, 5.7]
    review = "Dried plums, acacia honey, roasted walnuts, and dark chocolate in aroma and cup. Fine, well-balanced acidity; creamy and rich body. Long finish with notes of caramelized almonds and subtle essences of vanilla and smoked oak."
    response = insert_key(network, key, point, review, country, name)
    print(f">> Inserting Key: {key}, Country: {country}, Name: {name}")
    print(f">> Insertion status: {response['status']}.")
    print(f">> {response['message']}.")
    print(f">> Key Inserted with {response['hops']} hops.")

    ################################################################
    #                        LOOKUP KEY                            #
    ################################################################
    lower_bounds = [2023, 97, 5.7]
    upper_bounds = [2023, 97, 5.7]
    print("\nVerifying insertion through lookup: ")
    response = network.lookup(key, lower_bounds, upper_bounds, N=5)
    print(f">> Lookup status: {response['status']}.")
    print(f">> {response['message']}")
    print(f">> Key Found with {response['hops']} hops.")
    # ################################################################
    # #                        UPDATE KEY                            #
    # ################################################################
    print(
        """\n################################################################
#                        UPDATE KEY                            #
################################################################\n"""
    )
    # Update all points
    print("\nUpdating all points for Romania:\n")
    update_fields = {"attributes": {"price": 35.0}}
    network.update_key(key, updated_data=update_fields)

    # Update only the review
    print("Updating specific point for Taiwan:\n")
    taiwan_country_key = hash_key("Taiwan")
    update_feilds_that_have = {"review_date": 2019, "rating": 94, "price": 35.0}
    update_to = {"attributes": {"price": 36.0}}
    response = network.update_key(
        key=taiwan_country_key, updated_data=update_to, criteria=update_feilds_that_have
    )
    # ################################################################
    # #                        LOOKUP KEY                            #
    # ################################################################
    lower_bounds = [2000, 10, 0]
    upper_bounds = [2023, 100, 50]
    print("\nVerifying updates through lookup:")
    response = network.lookup(taiwan_country_key, lower_bounds, upper_bounds, N=5)
    print(f">> Lookup status: {response['status']}.")
    print(f">> {response['message']}")
    print(f">> Key Found with {response['hops']} hops.")
    print(f"Returned points: {response['points']}")
    # ################################################################
    # #                        DELETE KEY                            #
    # ################################################################
    print(
        """\n################################################################
#                        DELETE KEY                            #
################################################################\n"""
    )
    print(f"\nDelete key with value {taiwan_country_key}.")
    response = network.delete_key(taiwan_country_key)
    print(f">> Delete status: {response['status']}.")
    print(f">> {response['message']}")
    print(f">> Key Deleted with {response['hops']} hops.")
    # ################################################################
    # #                        LOOKUP KEY                            #
    # ################################################################
    lower_bounds = [2018, 90, 30.0]
    upper_bounds = [2019, 95, 40.0]
    print("\nVerifying deletion through lookup:\n")
    network.lookup(taiwan_country_key, lower_bounds, upper_bounds, N=5)

    print(
        """\n################################################################
#                        NETWORK STATE                         #
################################################################\n"""
    )
    for node_id in network.nodes.keys():
        if network.nodes[node_id].running:
            network.nodes[node_id].print_state()

    print(
        """\n################################################################
#                        NODE JOIN                             #
################################################################\n"""
    )
    node = ChordNode(network, node_id="2fec")
    node.start_server()
    network.node_join(node)
    time.sleep(2)
    print(
        """\n################################################################
#                        NETWORK STATE                         #
################################################################\n"""
    )
    for node_id in network.nodes.keys():
        if network.nodes[node_id].running:
            network.nodes[node_id].print_state()

    # ################################################################
    # #                        NODES LEAVE                           #
    # ################################################################
    print(
        """\n################################################################
#                        NODES LEAVE                           #
################################################################\n"""
    )
    time.sleep(2)
    for node in predefined_ids:
        node = network.nodes[node]
        if node.running:
            node.leave()
            time.sleep(3)
            print(f"\n>>>> State after node {node.node_id} left")
            for node in network.nodes.values():
                if node.running:
                    node.print_state()

    # running = True
    # while running:
    #     time.sleep(2)
    #     running = False
    #     for node in network.nodes.values():
    #         if node.running:
    #             running = True


if __name__ == "__main__":
    main()
