"""STARDRIFT entry point."""
import pygame

from game import StarDriftGame


def main():
    pygame.init()
    game = StarDriftGame()
    game.run()


if __name__ == "__main__":
    main()
