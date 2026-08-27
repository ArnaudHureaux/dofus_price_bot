##########
# Description: Maps a Dofus item `type` to its Marketplace (HDV) category.
#              Three HDVs exist: resource, equipment, consumable.
#              Anything not explicitly equipment/consumable defaults to
#              "resource" (covers the ~40 resource types without listing them).
##########

EQUIPMENT_TYPES = {
    "Amulette", "Anneau", "Bottes", "Cape", "Ceinture", "Chapeau",
    "Bouclier", "Sac à dos", "Dofus", "Trophée", "Équipement de percepteur",
    "Objet d'apparat", "Objet vivant",
    "Arc", "Baguette", "Bâton", "Dague", "Dagues", "Épée", "Faux",
    "Hache", "Lance", "Marteau", "Pelle", "Pioche",
}

CONSUMABLE_TYPES = {
    "Ballon", "Bière", "Boisson", "Boîte de fragments", "Bourse", "Cadeau",
    "Coffre", "Conteneur", "Document", "Éklâme", "Fée d'artifice", "Friandise",
    "Mimibiote", "Mots de haïku", "Objet utilisable", "Objet utilisable de Temporis",
    "Pain", "Parchemin d'attitude", "Parchemin de caractéristique",
    "Parchemin de sortilège", "Parchemin de titre", "Parchemin d'émoticônes",
    "Parchemin d'expérience", "Poisson comestible", "Popoche de Havre-Sac",
    "Potion", "Potion d'attitude", "Potion de conquête", "Potion de téléportation",
    "Prisme", "Sac de ressources", "Tatouage de la Foire du Trool", "Viande comestible",
}

RESOURCE_TYPES = {
    "Aile", "Alliage", "Bois", "Bourgeon", "Carapace", "Carte", "Céréale",
    "Champignon", "Clef", "Coquille", "Cuir", "Écorce",
    "Essence de gardien de donjon", "Étoffe", "Fleur", "Fragment de carte",
    "Fruit", "Galet", "Gelée", "Graine", "Haïku", "Huile", "Laine", "Légume",
    "Liquide", "Matériel d'alchimie", "Matériel d'exploration", "Métaria",
    "Minerai", "Nowel", "Œil", "Œuf", "Oreille", "Os", "Patte", "Peau",
    "Pierre brute", "Pierre précieuse", "Planche", "Plante", "Plume", "Poil",
    "Poisson", "Poudre", "Préparation", "Queue", "Rabmablague", "Racine",
    "Ressource de combat", "Ressource des Anomalies Temporelles",
    "Ressource des Songes", "Ressource diverse", "Ressources diverses",
    "Sève", "Substrat", "Teinture", "Vêtement", "Viande",
}


def hdv_for_type(item_type: str) -> str:
    """Return the HDV category for an item type: 'equipment', 'consumable', or 'resource'."""
    t = (item_type or "").strip()
    if t in EQUIPMENT_TYPES:
        return "equipment"
    if t in CONSUMABLE_TYPES:
        return "consumable"
    return "resource"
