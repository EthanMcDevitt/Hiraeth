class InventoryMixin:

    def item_by_id(self, category, item_id):
        return next((item for item in self.rules[category] if item['id'] == item_id), None)

    def item_name(self, category, item_id):
        item = self.item_by_id(category, item_id) if item_id else None
        return item['name'] if item else None

    def current_inventory(self):
        if self.inventory_owner is None:
            return self.game.setdefault('party_inventory', [])
        return self.game['party'][self.inventory_owner].setdefault('inventory', [])

    def transfer_choices(self):
        party = self.game['party']
        if self.inventory_owner is None:
            return list(range(len(party)))
        return [None] + [
            index for index in range(len(party))
            if index != self.inventory_owner
        ]

    def find_item(self, item_id):
        for category in ('weapons', 'armor', 'gear', 'spells'):
            item = self.item_by_id(category, item_id)
            if item:
                return item
        return None

    def inventory_slots(self, item_ids):
        return sum((self.find_item(item_id) or {}).get('slots', 1) for item_id in item_ids)

    def is_encumbered(self, member):
        strength = max(1, int(member.get('Stats', {}).get('STR', 10)))
        return self.inventory_slots(member.get('inventory', [])) > strength

    def buy_inventory_item(self):
        item = next((entry for entry in self.rules[self.inventory_category]
                     if entry['id'] == self.inventory_selected), None)
        if not item:
            return
        if self.inventory_category == 'spells':
            self.learn_inventory_spell()
            return
        location = self.game.get('location', {})
        if location.get('type') != 'town':
            self.message = 'Equipment can only be purchased in towns.'
            return
        if location.get('level', 1) + self.game.get('reputation', 0) <= 0:
            self.message = 'The town refuses to trade with the party at its current reputation.'
            return
        total_cost = item.get('cost', 0)
        if self.game['wealth'] < total_cost:
            self.message = f"Need {total_cost} Wealth for this purchase."
            return
        if self.inventory_owner is not None:
            member = self.game['party'][self.inventory_owner]
            capacity = max(1, int(member.get('Stats', {}).get('STR', 10))) * 2
            if self.inventory_slots(member.setdefault('inventory', [])) + item.get('slots', 1) > capacity:
                self.message = f"{member['Name']} cannot carry any more."
                return
            member['inventory'].append(item['id'])
        else:
            self.game.setdefault('party_inventory', []).append(item['id'])
        self.game['wealth'] -= total_cost
        self.game['day'] += 1
        self.message = f"Bought {item['name']} for {total_cost} Wealth."
        self.inventory_owned_index = None
        self.save()

    def learn_inventory_spell(self):
        if self.inventory_owner is None:
            self.message = 'Choose a character to learn a spell.'
            return
        spell = self.item_by_id('spells', self.inventory_selected)
        member = self.game['party'][self.inventory_owner]
        if not spell or spell['id'] in member.setdefault('known_spells', []):
            return
        if member.get('max_spells', 0) <= 0:
            self.message = f"{member['Name']} needs Shei ancestry or Sorcery rank 5 to learn spells."
            return
        if len(member['known_spells']) >= member['max_spells']:
            self.message = f"{member['Name']} already knows the maximum {member['max_spells']} spells."
            return
        member['known_spells'].append(spell['id'])
        self.message = f"{member['Name']} learned {spell['name']}; casting costs {spell['cost']} Magica."
        self.save()

    def transfer_inventory_item(self):
        if self.inventory_owned_index is None:
            return
        source = self.current_inventory()
        index = self.inventory_owned_index
        if index >= len(source):
            return
        item_id = source[index]
        item = self.find_item(item_id)
        if not item:
            return
        choices = self.transfer_choices()
        if not choices:
            return
        recipient_index = choices[self.inventory_recipient % len(choices)]
        if recipient_index is None:
            if self.inventory_owner is None:
                return
            destination = self.game.setdefault('party_inventory', [])
            destination.append(source.pop(index))
            self.message = f"Moved {item['name']} to the party stash."
        else:
            recipient = self.game['party'][recipient_index]
            capacity = max(1, int(recipient.get('Stats', {}).get('STR', 10))) * 2
            if self.inventory_slots(recipient.setdefault('inventory', [])) + item.get('slots', 1) > capacity:
                self.message = f"{recipient['Name']} cannot carry any more."
                return
            recipient['inventory'].append(source.pop(index))
            self.message = f"Moved {item['name']} to {recipient['Name']}."
        self.inventory_owned_index = None
        self.save()

    def equip_inventory_item(self):
        if self.inventory_owner is None or self.inventory_owned_index is None:
            return
        owned = self.current_inventory()
        if self.inventory_owned_index >= len(owned):
            return
        item_id = owned[self.inventory_owned_index]
        member = self.game['party'][self.inventory_owner]
        equipment = member.setdefault('equipment', {'weapon': None, 'armor': None, 'helmet': None, 'shield': None})
        weapon = self.item_by_id('weapons', item_id)
        armor = self.item_by_id('armor', item_id)
        if weapon:
            equipment['weapon'] = item_id
        elif armor:
            equipment[armor['kind']] = item_id
        else:
            return
        self.refresh_armor_points(member, fill_increase=True)
        self.message = f"{self.find_item(item_id)['name']} equipped."
        self.save()

    def unequip_inventory_item(self):
        if self.inventory_owner is None or self.inventory_owned_index is None:
            return
        owned = self.current_inventory()
        if self.inventory_owned_index >= len(owned):
            return
        item_id = owned[self.inventory_owned_index]
        member = self.game['party'][self.inventory_owner]
        equipment = member.get('equipment', {})
        for slot, equipped_id in equipment.items():
            if equipped_id == item_id:
                equipment[slot] = None
                self.refresh_armor_points(member)
                self.message = f"{self.find_item(item_id)['name']} unequipped."
                self.save()
                return

    def refresh_armor_points(self, member, fill_increase=False):
        equipment = member.get('equipment', {})
        armor_total = sum(
            (self.item_by_id('armor', equipment.get(slot)) or {}).get('ap', 0)
            for slot in ('armor', 'helmet', 'shield')
        )
        old_max = member.get('armor_ap_max', 0)
        member['armor_ap_broken'] = min(member.get('armor_ap_broken', 0), armor_total)
        armor_points = max(0, armor_total - member['armor_ap_broken'])
        member['armor_ap_now'] = min(member.get('armor_ap_now', old_max), armor_points)
        if fill_increase and armor_points > old_max:
            member['armor_ap_now'] += armor_points - old_max
        member['armor_ap_total'] = armor_total
        member['armor_ap_max'] = armor_points
