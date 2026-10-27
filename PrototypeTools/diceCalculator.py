import os
import sys

d4 = 4
d6 = 6
d8 = 8
d10 = 10
d12 = 12
d20 = 20
d100 = 100

def roll(numOfDice: int, numSides: int):
    """Rolls a number of dice and returns the total."""
    import random
    return sum(random.randint(1, numSides) for _ in range(numOfDice))

def fallDmg(ftFallen: int):
    #calculates fall damage based on the distance fallen
    if(ftFallen/10 > 20):
        ftFallen = 200
    return roll(ftFallen//10, 6)

def main():
    print("--- D&D Dice & Damage Simulator ---")
    
    # Example 1: Testing a manual dice roll
    fireball_damage = roll(8, d6)
    print(f"Fireball damage (8d6): {fireball_damage}")
    
    # Example 2: Testing the fall damage function
    distance = 50
    damage = fallDmg(distance)
    print(f"Fall damage from {distance} feet: {damage}")

if __name__ == "__main__":
    main()