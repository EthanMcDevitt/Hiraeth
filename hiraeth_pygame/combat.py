if __package__:
    from .shared import (
        modifier,
        pygame,
        random,
    )
else:
    from shared import (
        modifier,
        pygame,
        random,
    )


class CombatMixin:

    def queue_combat_animation(self, source_type, source_index, target_type, target_index):
        now = pygame.time.get_ticks()
        start_at = max(now, self.animation_next_at)
        self.animation_next_at = start_at + 850
        animation = {
            'source_type': source_type,
            'source_index': source_index,
            'target_type': target_type,
            'target_index': target_index,
            'start_at': start_at,
            'end_at': start_at + 1200,
            'result': None,
        }
        self.attack_animations.append(animation)
        return animation

    def alive_party(self):
        return [member for member in self.game['party'] if member['health'] > 0]

    @staticmethod
    def trait_rank(member, name):
        try:
            return max(0, int(member.get('Traits', {}).get(name, 0) or 0))
        except (TypeError, ValueError):
            return 0

    def weapon_training(self, member, weapon):
        if weapon is None:
            weapon_type = 'melee'
            advanced = False
            stat = 'STR'
        else:
            weapon_type = (
                'melee'
                if weapon['range'].lower() == 'close' or weapon['attack_stat'] == 'STR'
                else 'ranged'
            )
            advanced = 'advanced' in weapon.get('traits', '').lower()
            stat = 'STR' if weapon_type == 'melee' else 'AGI'
        required_rank = (1 if weapon_type == 'melee' else 2) + (2 if advanced else 0)
        rank = self.trait_rank(member, 'Martial Training')
        return rank >= required_rank, stat, rank >= 5

    def finish_battle_if_needed(self):
        battle = self.game['battle']
        if not self.alive_party():
            self.game['mode'] = 'lost'
            self.game['battle'] = None
            self.game['log'].insert(0, 'The party falls in battle.')
        elif all(enemy['health_now'] <= 0 for enemy in battle['enemies']):
            self.game['battle'] = None
            self.game['wealth'] += self.journey['victory_wealth']
            self.game['reputation'] += self.journey['victory_reputation']
            self.game['log'].insert(0, self.texts['victory_log'].format(
                wealth=self.journey['victory_wealth'],
                reputation=self.journey['victory_reputation'],
            ))
            self.continue_after_travel_turn()

    def enemy_turn(self):
        battle = self.game['battle']
        guarded = {
            int(index) for index, plan in battle.get('plans', {}).items()
            if plan.get('kind') == 'guard'
        }
        for enemy_index, enemy in enumerate(battle['enemies']):
            if enemy['health_now'] <= 0 or not self.alive_party():
                continue
            if enemy.get('blinded') or enemy.get('calmed'):
                self.game['log'].insert(0, f"{enemy['name']} cannot attack this round.")
                continue
            target = random.choice(self.alive_party())
            target_index = self.game['party'].index(target)
            if target.get('rank', 'front') == 'back':
                for front_index, front in enumerate(self.game['party']):
                    if (
                        front['health'] > 0
                        and front.get('rank', 'front') == 'front'
                        and enemy['health_now'] > 0
                    ):
                        self.resolve_attack(front_index, enemy_index, opportunity=True)
                if enemy['health_now'] <= 0:
                    self.game['log'].insert(0, f"{enemy['name']} is stopped by the front row's opportunity attacks.")
                    continue
            animation = self.queue_combat_animation(
                'foe', enemy_index, 'party', target_index,
            )
            defense_bonus = max(modifier(target, 'STR'), modifier(target, 'AGI'))
            defense_bonus_percent = defense_bonus * 5
            defense_rolls = [random.randint(1, 100)]
            encumbered = self.is_encumbered(target)
            check_mode = ''
            if target_index in guarded and not encumbered:
                defense_rolls.append(random.randint(1, 100))
                defense_roll = max(defense_rolls)
                check_mode = ' (advantage: guard)'
            elif encumbered and target_index not in guarded:
                defense_rolls.append(random.randint(1, 100))
                defense_roll = min(defense_rolls)
                check_mode = ' (disadvantage: encumbered)'
            else:
                defense_roll = defense_rolls[0]
            hit_chance = enemy['chance_to_hit']
            effective_hit_chance = max(
                0,
                min(100, hit_chance - defense_bonus_percent),
            )
            defense_check = (
                f"Defense: d100 {defense_rolls}{check_mode} vs hit chance "
                f"{hit_chance}% - best STR/AGI "
                f"({defense_bonus:+d} × 5 = {defense_bonus_percent:+d}%) "
                f"= {effective_hit_chance}% "
                f"({'hit' if defense_roll <= effective_hit_chance else 'avoided'})"
            )
            animation['result'] = defense_roll <= effective_hit_chance
            if not animation['result']:
                self.game['log'].insert(
                    0, f"{target['Name']} avoids {enemy['name']}'s attack ({defense_check})."
                )
                continue
            damage = max(
                self.combat['minimum_damage'],
                enemy['damage'] - max(0, modifier(target, 'CON') // self.combat['constitution_reduction_divisor']),
            )
            if target_index in guarded:
                damage = max(self.combat['minimum_damage'], damage // self.combat['guard_reduction_divisor'])
            if target_index in battle.get('shielded', []):
                damage = max(self.combat['minimum_damage'], damage - 1)
            if target.get('armor_ap_now', 0) > 0:
                target['armor_ap_now'] -= 1
                self.game['log'].insert(
                    0,
                    f"{target['Name']}'s armor absorbs {enemy['name']}'s attack "
                    f"(1 AP broken; {defense_check}).",
                )
                continue
            temporary = min(target.get('temporary_health', 0), damage)
            target['temporary_health'] = target.get('temporary_health', 0) - temporary
            damage -= temporary
            target['health'] -= damage
            self.game['log'].insert(
                0,
                self.texts['enemy_hit_log'].format(
                    monster=enemy['name'], character=target['Name'], damage=damage,
                ) + f" ({defense_check}; {enemy['damage']} base damage - CON mitigation).",
            )
        battle['guarding'] = []
        battle['shielded'] = []
        battle['elemental_shielded'] = []
        self.finish_battle_if_needed()
        if self.game['mode'] == 'combat':
            battle['plans'] = {}
            battle['targeting'] = None
            battle['planning_actor'] = next(
                (index for index, member in enumerate(self.game['party']) if member['health'] > 0),
                None,
            )
            battle['phase'] = 'planning'
            battle['round'] = battle.get('round', 1) + 1

    @staticmethod
    def roll_dice(expression):
        return Hiraeth.roll_dice_details(expression)[1]

    @staticmethod
    def roll_dice_details(expression):
        try:
            count_text, sides_text = expression.lower().split('d', 1)
            count = int(count_text) if count_text else 1
            sides = int(sides_text)
        except (AttributeError, ValueError):
            return [1], 1
        faces = [random.randint(1, sides) for _ in range(max(1, count))]
        return faces, sum(faces)

    @staticmethod
    def format_dice(expression, faces):
        return f"{expression} {faces} = {sum(faces)}"

    @staticmethod
    def format_modifier(name, value):
        return f"{name} {value:+d}"

    def resolve_attack(self, actor_index, enemy_index, opportunity=False):
        battle = self.game.get('battle')
        if not battle or not 0 <= enemy_index < len(battle['enemies']):
            return
        actor = self.game['party'][actor_index]
        enemy = battle['enemies'][enemy_index]
        if enemy['health_now'] <= 0:
            self.game['log'].insert(0, f"{enemy['name']} is no longer a valid target.")
            return
        animation = self.queue_combat_animation(
            'party', actor_index, 'foe', enemy_index,
        )
        weapon = self.item_by_id('weapons', actor.get('equipment', {}).get('weapon'))
        trained, attack_stat, master_training = self.weapon_training(actor, weapon)
        attack_rolls = [random.randint(1, 20)]
        encumbered = self.is_encumbered(actor)
        if encumbered:
            attack_rolls.append(random.randint(1, 20))
        roll = min(attack_rolls)
        damage_dice = weapon['damage'] if weapon else '1d4'
        damage_faces, damage_total = self.roll_dice_details(damage_dice)
        attribute_bonus = modifier(actor, attack_stat) if trained else 0
        training_bonus = 2 if master_training else 0
        attack_bonus = attribute_bonus + training_bonus
        attack_total = roll + attack_bonus
        hit = attack_total >= enemy['defense']
        animation['result'] = hit
        attack_modifiers = [
            f"{attack_stat} modifier {attribute_bonus:+d}" if trained else 'untrained (+0)'
        ]
        if training_bonus:
            attack_modifiers.append(f"Martial Training {training_bonus:+d}")
        attack_check = (
            f"Attack: d20 {attack_rolls}"
            + (' (disadvantage: encumbered)' if encumbered else '')
            + f" + {' + '.join(attack_modifiers)} = {attack_total} "
            f"vs DEF {enemy['defense']} ({'hit' if hit else 'miss'})"
        )
        damage_bonus = modifier(actor, attack_stat) if trained else 0
        if trained:
            damage = max(0, damage_total + damage_bonus)
        else:
            damage = damage_total
        damage_check = (
            f"Damage: {self.format_dice(damage_dice, damage_faces)}"
            + (f" {self.format_modifier(attack_stat, damage_bonus)} = {damage}" if trained else '')
        )
        if hit:
            enemy['health_now'] -= damage
            message = self.texts['player_hit_log'].format(
                character=actor['Name'], monster=enemy['name'], damage=damage,
            ) + f" ({attack_check}; {damage_check})."
            if opportunity:
                message = f"{actor['Name']} makes an opportunity attack: {message}"
            self.game['log'].insert(0, message)
        else:
            message = self.texts['player_miss_log'].format(
                character=actor['Name'], monster=enemy['name'],
            ) + f" ({attack_check}; {damage_check}, damage not dealt)."
            if opportunity:
                message = f"{actor['Name']} misses with an opportunity attack: {message}"
            self.game['log'].insert(0, message)

    def resolve_spell(self, spell_id, actor_index, target_index, in_combat):
        actor = self.game['party'][actor_index]
        spell = self.item_by_id('spells', spell_id)
        battle = self.game.get('battle') if in_combat else None
        if not spell or spell_id not in actor.get('known_spells', []) or actor['magica_now'] < spell['cost']:
            return False
        if spell['target'] == 'ally':
            if target_index is None or not 0 <= target_index < len(self.game['party']):
                return False
            target = self.game['party'][target_index]
            if target['health'] <= 0:
                return False
        else:
            if not battle or target_index is None or not 0 <= target_index < len(battle['enemies']):
                return False
            target = battle['enemies'][target_index]
            if target['health_now'] <= 0:
                return False

        animation = None
        if in_combat:
            animation = self.queue_combat_animation(
                'party', actor_index,
                'party' if spell['target'] == 'ally' else 'foe',
                target_index,
            )
        effect = spell_id
        roll_notes = []
        if effect == 'heal_wounds':
            faces, total = self.roll_dice_details('1d8')
            restored = min(total, target['max_health'] - target['health'])
            roll_notes.append(f"{self.format_dice('1d8', faces)}; restores {restored}")
            if restored <= 0:
                self.game['log'].insert(
                    0, f"{actor['Name']}'s {spell['name']} roll: {roll_notes[-1]} Health."
                )
                return False
            target['health'] += restored
            result = f"{actor['Name']} heals {target['Name']} for {restored} Health."
        elif effect == 'respite':
            faces, total = self.roll_dice_details('1d8')
            restored = min(total, target['max_stamina'] - target['stamina_now'])
            roll_notes.append(f"{self.format_dice('1d8', faces)}; restores {restored}")
            if restored <= 0:
                self.game['log'].insert(
                    0, f"{actor['Name']}'s {spell['name']} roll: {roll_notes[-1]} Stamina."
                )
                return False
            target['stamina_now'] += restored
            result = f"{actor['Name']} restores {restored} Stamina to {target['Name']}."
        elif effect == 'fortify_health':
            faces, restored = self.roll_dice_details('1d6')
            roll_notes.append(self.format_dice('1d6', faces))
            target['temporary_health'] = target.get('temporary_health', 0) + restored
            result = f"{target['Name']} gains {restored} temporary Health."
        elif effect == 'absorb_health':
            faces, total = self.roll_dice_details('1d6')
            drained = min(target['health_now'], total)
            roll_notes.append(f"{self.format_dice('1d6', faces)}; drains {drained}")
            if drained <= 0:
                self.game['log'].insert(0, f"{spell['name']} roll: {roll_notes[-1]} Health.")
                return False
            target['health_now'] -= drained
            restored = min(drained, actor['max_health'] - actor['health'])
            actor['health'] += restored
            result = f"{actor['Name']} drains {drained} Health from {target['name']}."
        elif effect in ('harm', 'flame', 'frost', 'lightning', 'repel_undead'):
            attack_rolls = [random.randint(1, 20)]
            encumbered = self.is_encumbered(actor)
            if encumbered:
                attack_rolls.append(random.randint(1, 20))
            attack_roll = min(attack_rolls)
            will_bonus = modifier(actor, 'WIL')
            attack_total = attack_roll + will_bonus
            hit = attack_total >= target['defense']
            if animation:
                animation['result'] = hit
            attack_check = (
                f"Spell attack: d20 {attack_rolls}"
                + (' (disadvantage: encumbered)' if encumbered else '')
                + f" + WIL modifier {will_bonus:+d} = {attack_total} "
                f"vs DEF {target['defense']} ({'hit' if hit else 'miss'})"
            )
            roll_notes.append(attack_check)
            if not hit:
                result = f"{actor['Name']}'s {spell['name']} misses {target['name']} ({attack_check})."
            else:
                dice = {
                    'harm': '2d4', 'flame': '2d4', 'frost': '1d6',
                    'lightning': '1d6', 'repel_undead': '1d8',
                }[effect]
                damage_faces, damage = self.roll_dice_details(dice)
                roll_notes.append(f"Damage: {self.format_dice(dice, damage_faces)}")
                target['health_now'] -= damage
                result = f"{spell['name']} deals {damage} damage to {target['name']} ({attack_check}; {roll_notes[-1]})."
        elif effect in ('exhaust', 'depress'):
            pool = 'stamina_now' if effect == 'exhaust' else 'magica_now'
            maximum = max(0, target.get(pool, target.get('attack', 1) * 2))
            faces, total = self.roll_dice_details('2d4')
            drained = min(maximum, total)
            roll_notes.append(f"{self.format_dice('2d4', faces)}; drains {drained}")
            target[pool] = maximum - drained
            result = f"{spell['name']} drains {drained} {pool.removesuffix('_now').title()} from {target['name']}."
        elif effect == 'blind':
            target['blinded'] = True
            result = f"{target['name']} is blinded."
        elif effect == 'calm':
            target['calmed'] = True
            result = f"{target['name']} is calmed and ceases fighting."
        elif effect in ('shield', 'elemental_shield'):
            target.setdefault('effects', []).append(effect)
            if in_combat:
                battle.setdefault(effect, []).append(target_index)
            result = f"{spell['name']} protects {target['Name']}."
        elif effect == 'antidote':
            effects = target.setdefault('effects', [])
            if 'poisoned' not in effects:
                return False
            effects.remove('poisoned')
            result = f"{actor['Name']} cures poison on {target['Name']}."
        elif effect == 'rally':
            target['effects'] = [
                value for value in target.get('effects', [])
                if value not in ('fear', 'charm', 'frenzy', 'demoralize', 'calm')
            ]
            result = f"{actor['Name']} rallies {target['Name']}."
        elif effect == 'dispel_magic':
            target['effects'] = []
            result = f"{actor['Name']} dispels magic from {target['Name']}."
        else:
            return False

        actor['magica_now'] -= spell['cost']
        if animation and animation['result'] is None:
            animation['result'] = 'CAST'
        if roll_notes and effect not in ('harm', 'flame', 'frost', 'lightning', 'repel_undead'):
            result += f" ({'; '.join(roll_notes)})."
        self.game['log'].insert(0, result)
        return True

    def cast_spell(self, spell_id, actor_index, target_index, in_combat=False):
        if self.resolve_spell(spell_id, actor_index, target_index, in_combat):
            if in_combat:
                self.finish_battle_if_needed()
            self.message = 'Spell cast.'
            self.save()
            return True
        self.message = 'That spell cannot affect the selected target or the character lacks Magica.'
        return False

    def plan_move(self, actor_index, kind, target_index=None, spell_id=None):
        battle = self.game.get('battle')
        if not battle or battle.get('phase') != 'planning' or actor_index is None:
            return
        plan = {'kind': kind}
        if target_index is not None:
            plan['target'] = target_index
        if spell_id:
            plan['spell_id'] = spell_id
        plans = battle.setdefault('plans', {})
        plans[str(actor_index)] = plan
        battle['targeting'] = None
        battle['planning_actor'] = next(
            (
                index for index, member in enumerate(self.game['party'])
                if member['health'] > 0 and str(index) not in plans
            ),
            None,
        )
        self.save()

    def resolve_party_moves(self):
        battle = self.game.get('battle')
        if not battle or battle.get('phase') != 'planning':
            return
        living = [index for index, member in enumerate(self.game['party']) if member['health'] > 0]
        if not living or not all(str(index) in battle.get('plans', {}) for index in living):
            return
        battle['phase'] = 'resolving'
        battle['targeting'] = None
        for actor_index in living:
            plan = battle['plans'][str(actor_index)]
            if plan['kind'] == 'attack':
                self.resolve_attack(actor_index, plan['target'])
            elif plan['kind'] == 'spell':
                self.resolve_spell(plan['spell_id'], actor_index, plan['target'], in_combat=True)
            elif plan['kind'] == 'switch_rank':
                member = self.game['party'][actor_index]
                member['rank'] = 'back' if member.get('rank', 'front') == 'front' else 'front'
                self.game['log'].insert(
                    0, f"{member['Name']} moves to the {member['rank']} row."
                )
            if self.game['mode'] != 'combat':
                break
            self.finish_battle_if_needed()
            if self.game['mode'] != 'combat':
                break
        if self.game['mode'] == 'combat':
            self.enemy_turn()
        self.save()
