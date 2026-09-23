import unittest
from world_controller import quest_requests_attack

class QuestCombat(unittest.TestCase):
    def test_actual_house_objective_exposes_ordinary_attack(self):
        house={'name':'Mr. House','kind':43,'distance':350}
        self.assertTrue(quest_requests_attack(house,'kill or disable mr. house.'))
        self.assertFalse(quest_requests_attack(house,'talk to mr. house.'))
        self.assertFalse(quest_requests_attack(house,'kill benny, then talk to mr. house.'))

    def test_actor_identity_range_and_name_boundary(self):
        self.assertFalse(quest_requests_attack({'name':'Mr. House','kind':23,'distance':30},'kill mr. house.'))
        self.assertFalse(quest_requests_attack({'name':'Mr. House','kind':43,'distance':2100},'kill mr. house.'))
        self.assertFalse(quest_requests_attack({'name':'Ben','kind':42,'distance':30},'kill benny.'))

if __name__=='__main__':unittest.main()
