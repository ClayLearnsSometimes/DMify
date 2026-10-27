import os
import sys

global stren
global dex
global con
global int
global wis
global char


def find_modifier(score: int):
    """Calculates the ability modifier based on the ability score."""
    return (score - 10) // 2

def output_modifiers():
    """Outputs the ability modifiers for each ability score."""
    print(f"Strength modifier: {find_modifier(stren)}")
    print(f"Dexterity modifier: {find_modifier(dex)}")
    print(f"Constitution modifier: {find_modifier(con)}")
    print(f"Intelligence modifier: {find_modifier(int)}")
    print(f"Wisdom modifier: {find_modifier(wis)}")
    print(f"Charisma modifier: {find_modifier(char)}")

def main():
    print("This is the pointBuy module. It currently has no functionality.")
    global stren
    global dex
    global con
    global int
    global wis
    global char

    stren = int(input("Enter a strength score: "))
    dex = int(input("Enter a dexterity score: "))
    con = int(input("Enter a constitution score: "))
    int = int(input("Enter a intelligence score: "))
    wis = int(input("Enter a wisdom score: "))
    char = int(input("Enter a charisma score: "))
    
    output_modifiers()

# 2. Tell Python to run the main function when this file is executed
if __name__ == "__main__":
    main()