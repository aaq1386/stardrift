"""Non-blocking credit economy for STARDRIFT."""

from queue import Queue
from threading import Thread

from database import Database


class Economy:
    BRICK_REWARDS = {1: 3, 2: 5, 3: 7}
    PADDLE_HITS_PER_REWARD = 50
    PADDLE_HIT_REWARD = 15
    FIRST_STAGE_REWARD = 30
    STAGE_REWARD_INCREMENT = 5

    def __init__(self, database=None):
        self.db = database or Database()

        # Read the profile once, not on every rendered frame.
        self._credits = self.db.get_profile()["credits"]

        self.run_paddle_hits = 0
        self.jobs = Queue()
        self.results = Queue()
        self._request_id = 0
        self.worker = Thread(
            target=self._database_worker,
            name="STARDRIFT-Database",
            daemon=True,
        )
        self.worker.start()

    @property
    def credits(self):
        """Return the cached balance without accessing SQLite."""
        return self._credits

    def _database_worker(self):
        while True:
            job = self.jobs.get()
            try:
                if job is None:
                    return

                operation, *args = job

                if operation == "credits":
                    self.db.add_credits(*args)
                elif operation == "stat":
                    self.db.record_stat(*args)
                elif operation == "shop_purchase":
                    request_id, shop, upgrade_key = args
                    try:
                        success, message = shop.purchase(upgrade_key)
                        items = shop.get_items()
                    except Exception as exc:
                        print(f"[Database worker] Shop purchase failed: {exc}")
                        success = False
                        message = "Purchase failed. Please try again."
                        items = None
                    self.results.put((request_id, success, message, items))

            except Exception as exc:
                print(f"[Database worker] Failed to save data: {exc}")
            finally:
                self.jobs.task_done()

    def request_shop_purchase(self, shop, upgrade_key):
        """Queue a shop purchase after all previously queued database jobs."""
        self._request_id += 1
        request_id = self._request_id
        self.jobs.put(("shop_purchase", request_id, shop, upgrade_key))
        return request_id

    def _award(self, amount, reason):
        amount = int(amount)
        if amount <= 0:
            return

        # Update the HUD immediately; persist asynchronously.
        self._credits += amount
        self.jobs.put(("credits", amount, reason))

    def start_run(self, record_game=True):
        self.run_paddle_hits = 0
        if record_game:
            self.jobs.put(("stat", "games_played", 1))

    def brick_destroyed(self, max_hp):
        max_hp = int(max_hp)
        reward = self.BRICK_REWARDS.get(
            max_hp, 12 if max_hp > 3 else 5
        )

        self._award(reward, f"brick_destroyed_hp_{max_hp}")
        self.jobs.put(("stat", "bricks_destroyed", 1))
        return reward

    def paddle_hit(self):
        self.run_paddle_hits += 1

        # No synchronous database write for each paddle collision.
        if self.run_paddle_hits % self.PADDLE_HITS_PER_REWARD == 0:
            self._award(
                self.PADDLE_HIT_REWARD,
                f"paddle_hits_{self.run_paddle_hits}",
            )
            return self.PADDLE_HIT_REWARD

        return 0

    def stage_cleared(self, level):
        level = max(1, int(level))
        reward = (
            self.FIRST_STAGE_REWARD
            + (level - 1) * self.STAGE_REWARD_INCREMENT
        )

        self._award(reward, f"stage_cleared_{level}")
        self.jobs.put(("stat", "stages_cleared", 1))
        return reward

    def close(self):
        """Wait for pending writes before the game exits."""
        self.jobs.join()
        self.jobs.put(None)
        self.worker.join()
