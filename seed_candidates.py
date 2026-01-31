import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voter_vision.settings')
django.setup()

from candidates.models import Candidate

def seed_data():
    candidates = [
        {
            "name": "KP Sharma Oli",
            "party": "CPN-UML",
            "province": "1",
            "bio": "Former Prime Minister and Chairman of CPN-UML. Known for his nationalist stance and infrastructure projects like the Melamchi water project and cross-border connectivity.",
            "past_work": "Served as PM multiple times. Led the 2015 blockade response. Focused on 'Prosperous Nepal, Happy Nepali'. Pushed for railway connectivity with China and India. Initiated social security schemes for workers.",
            "is_featured": True
        },
        {
            "name": "Pushpa Kamal Dahal (Prachanda)",
            "party": "CPN (Maoist Centre)",
            "province": "3",
            "bio": "Current Prime Minister and Chairman of Maoist Centre. Former rebel leader who led the 10-year People's War before joining mainstream politics.",
            "past_work": "Key architect of the Comprehensive Peace Agreement. Focused on inclusion, federalism, and secularism in the 2015 Constitution. Currently leading a coalition government focusing on economic recovery and good governance.",
            "is_featured": True
        },
        {
            "name": "Sher Bahadur Deuba",
            "party": "Nepali Congress",
            "province": "7",
            "bio": "President of Nepali Congress and former multi-time Prime Minister. A veteran politician with deep roots in democratic movements.",
            "past_work": "Led several coalition governments. Historically focused on democratic consolidation and international relations. Known for his pragmatism in coalition politics.",
            "is_active": True
        },
        {
            "name": "Rabi Lamichhane",
            "party": "Rastriya Swatantra Party",
            "province": "3",
            "bio": "Former journalist and Chairman of Rastriya Swatantra Party (RSP). Entered politics with a platform of anti-corruption and service delivery reform.",
            "past_work": "Hosted 'Sidha Kura Janata Sanga' which exposed corruption and administrative failures. As Home Minister, initiated crackdowns on gold smuggling and forged documents. Strong advocate for digital governance.",
            "is_featured": True
        },
        {
            "name": "Balen Shah",
            "party": "Independent",
            "province": "3",
            "bio": "Mayor of Kathmandu Metropolitan City. A structural engineer and rapper who won as an independent candidate, sparking a nationwide independent movement.",
            "past_work": "Transformed waste management in Kathmandu. Initiated digital mapping of city services. Led the demolition of illegal structures on public land. Focused on cultural heritage preservation and 'Clean Kathmandu' initiative.",
            "is_active": True
        },
        {
            "name": "Gagan Thapa",
            "party": "Nepali Congress",
            "province": "3",
            "bio": "General Secretary of Nepali Congress and former Health Minister. A popular youth leader known for his oratory skills and advocacy for healthcare reforms.",
            "past_work": "Initiated the health insurance scheme in Nepal as Health Minister. Vocal advocate for democratic reforms within the party. Active in earthquake reconstruction and COVID-19 response planning.",
            "is_active": True
        },
        {
            "name": "Harka Sampang",
            "party": "Independent",
            "province": "1",
            "bio": "Mayor of Dharan Sub-Metropolitan City. Emerged from grass-roots activism, specifically focusing on water supply issues in Dharan.",
            "past_work": "Led massive tree-planting campaigns. Mobilized voluntary labor (Shramdaan) for water projects, successfully bringing water to Dharan. Known for his simple lifestyle and direct engagement with citizens on social media.",
            "is_active": True
        }
    ]

    for data in candidates:
        candidate, created = Candidate.objects.get_or_create(
            name=data["name"],
            defaults={
                "party": data["party"],
                "province": data["province"],
                "bio": data["bio"],
                "past_work": data["past_work"],
                "is_featured": data.get("is_featured", False),
                "is_active": data.get("is_active", True)
            }
        )
        if created:
            print(f"Created candidate: {candidate.name}")
        else:
            print(f"Candidate already exists: {candidate.name}")

if __name__ == "__main__":
    seed_data()
