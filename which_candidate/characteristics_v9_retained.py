"""Field-directed readings of retained originals, without proxy classifications."""


def additional_reviews(claim, education):
    def jobs(values, fragment):
        return claim(
            "profession",
            {"reported_careers": values},
            fragment,
            reason="Explicit candidate career report; multiple careers and current versus "
            "historical work are retained without forcing a principal occupational family.",
        )

    def office(value, fragment):
        return claim(
            "prior_elected_office",
            {"reported_office": value},
            fragment,
            reason="Explicit public-office history, not a complete history before first House "
            "entry and not evidence of paid non-elected government employment.",
        )

    def government(value, fragment, *, factual=True, reason=None):
        return claim(
            "other_government",
            {"reported_role": value},
            fragment,
            factual=factual,
            reason=reason
            or "Explicit civilian public-employment report, distinct from elected office, "
            "military service, advocacy and volunteering; exact dates remain unspecified.",
        )

    return {
        "campaign-140487-home": [
            education("earning a bachelor’s degree in education", "bachelors"),
            jobs(
                ["car dealership work", "real estate work", "public school teacher"],
                "After working in car dealerships and real estate",
            ),
            government(
                "Teacher, Lockhart Independent School District",
                "becoming a teacher in the Lockhart Independent School District",
            ),
        ],
        "campaign-205786-bio1": [
            education("earned an MBA from Felician University", "masters"),
            jobs(
                ["farmer", "entrepreneur", "corporate team supervisor", "professional baseball"],
                "Michael A. Chiaradio is a farmer and entrepreneur",
            ),
        ],
        "campaign-219735-bio2": [
            office("Pelham City Council", "During my time on the Pelham City Council"),
        ],
        "campaign-219764-home": [
            office(
                "Arizona State Representative",
                "Amish has represented parts of Arizona’s First Congressional District as a State Representative",
            ),
        ],
        "campaign-219770-bio1": [
            office("President of the Navajo Nation", "As President of the Navajo Nation"),
        ],
        "campaign-219877-home": [
            office("Mayor of Dublin", "the first Latina Mayor of Dublin"),
        ],
        "campaign-219895-home": [
            jobs(
                ["teaching", "community organizing"],
                "from earning a PhD to teaching and organizing",
            ),
        ],
        "campaign-219910-home": [
            education("Master’s in Organizational Leadership from Woodbury University", "masters"),
            jobs(
                ["caregiver", "activist", "community organizer"],
                "Mother of five, caregiver, activist, and community organizer",
            ),
            claim(
                "prior_elected_office",
                {
                    "reported_role": "Two terms President and one term Vice President, Sun Valley Area Neighborhood Council"
                },
                "Two terms President of Sun Valley Area Neighborhood Council",
                factual=False,
                reason="Council leadership explicitly reported, but this statement alone does "
                "not establish an elected rather than appointed/advisory position.",
            ),
        ],
        "campaign-219922-bio1": [
            jobs(
                ["housing advocate", "reentry leader"],
                "professional expertise of a housing advocate and reentry leader",
            ),
            claim(
                "prior_elected_office",
                {"reported_role": "President, Highland Park Neighborhood Council"},
                "President of the Highland Park Neighborhood Council",
                factual=False,
                reason="Council presidency is explicit; elected versus appointed/advisory "
                "status is not established by this statement.",
            ),
        ],
        "campaign-219951-bio1": [
            office("San Diego City Council", "Marni von Wilpert is a San Diego City Councilmember"),
        ],
        "campaign-219963-bio1": [
            education("to pursue an electrical engineering degree"),
            jobs(
                ["engineer", "Foreign Affairs Officer under AAAS fellowship"],
                "worked as an engineer at the Johns Hopkins University Applied Physics Laboratory",
            ),
            government(
                "AAAS fellow, State Department Foreign Affairs Officer, selected in 2021",
                "joined the U.S. Department of State as a Foreign Affairs Officer",
                factual=False,
                reason="Explicit government-hosted fellowship; neither direct paid federal "
                "employment nor the fellowship's employer/paymaster is established. "
                "University defense research and relatives' service are not military service.",
            ),
        ],
        "campaign-219967-bio1": [
            office(
                "Sacramento City Council, elected in 2020",
                "Since being elected in 2020, Councilmember Vang",
            ),
        ],
        "campaign-220086-home": [
            education("where she earned a Juris Doctorate", "doctoral_or_professional"),
            jobs(["AT&T employee", "federal service at EPA"], "while working for AT&T"),
        ],
        "campaign-220117-bio1": [
            office(
                "Sarasota mayor and city commissioner",
                "a former Sarasota mayor and city commissioner",
            ),
            jobs(
                ["college vice president and dean", "nonprofit co-founder"],
                "the former vice president and dean of executive and continuing education at Eckerd College",
            ),
            education("When he went to Georgetown"),
        ],
        "campaign-220119-bio1": [
            jobs(
                [
                    "farmhand",
                    "janitor",
                    "messenger",
                    "store clerk",
                    "regional planning",
                    "UN Food and Agriculture Organization",
                ],
                "27 years with the UN Food and Agriculture Organization",
            ),
            government(
                "Regional planning council work and UN Food and Agriculture Organization",
                "6 years working with regional planning councils",
                factual=False,
                reason="Public/intergovernmental service reports retained, but council "
                "employment terms and eligibility of international-organization employment "
                "under the existing governmental definition are unresolved.",
            ),
        ],
        "campaign-220135-home": [
            government(
                "White House Fellow, Department of Education",
                "served as a White House Fellow at the Department of Education",
                factual=False,
                reason="A fellowship is explicit; this statement does not establish direct "
                "paid government employment or its employment terms.",
            ),
        ],
        "campaign-220139-bio1": [
            education("class at the University of Miami School of Law"),
            office(
                "Mayor of Miami Gardens, eight years",
                "serving as Mayor of my hometown for eight years",
            ),
        ],
        "campaign-220176-bio1": [
            claim(
                "military",
                {
                    "reported_service": "U.S. Army, enlisted 1978, retired Lieutenant Colonel after 26 years"
                },
                "Enlisting in the United States Army as a Military Policewoman in 1978",
                analysis=True,
                timing="explicit_1978_enlistment_and_26_year_retired_service",
                reason="Explicit multiyear personal military service beginning in 1978 and "
                "completed after 26 years, before the election; not inferred from advocacy.",
            ),
            education("pursued another degree as a Nuclear Medicine Technologist"),
            jobs(
                ["Army officer", "government contractor", "VA healthcare work"],
                "Maura became a government contractor",
            ),
            government(
                "Government contractor, followed by healthcare work at Atlanta VA",
                "her work with the Atlanta Veterans Affairs Healthcare System",
                factual=False,
                reason="Contracting is explicit and distinct from government employment. "
                "The later VA healthcare work does not specify the employing entity or "
                "whether it was direct rather than contracted employment.",
            ),
        ],
        "campaign-220190-home": [
            jobs(
                ["Army medical readiness policy", "nursing"],
                "six years at the Pentagon analyzing and developing medical readiness policies",
            ),
        ],
        "campaign-220238-bio2": [
            claim(
                "age",
                {"reported_age": 36, "reference_date": None},
                "Kaylee Peterson is a 36-year-old working mom",
                timing="undated_reported_age_reference_not_known",
                reason="Literal reported age with no qualified reference date. Retrieval "
                "in 2026 does not establish when the biography's age was written; no "
                "birth interval or election-day age is assigned.",
            ),
        ],
        "campaign-220320-bio1": [
            jobs(
                ["Marine Corps bandsman", "farm work"],
                "joined the United States Marine Corps in 2008 as a Bandsman",
            ),
        ],
        "campaign-220399-bio1": [
            jobs(["mechanic", "caregiver", "activist"], "I’m a mechanic by trade"),
        ],
        "campaign-220616-bio1": [
            government("Current county employee", "current county employee"),
        ],
        "campaign-220646-home": [
            education("Fred graduated from West Point"),
        ],
        "campaign-220649-bio2": [
            jobs(["chemist"], "Bethany Mann is a chemist"),
        ],
        "campaign-220652-bio2": [
            jobs(
                [
                    "Air Force biomedical equipment engineer",
                    "attorney",
                    "Assistant Attorney General",
                ],
                "current role as Assistant Attorney General for the State of Missouri",
            ),
        ],
        "campaign-220661-bio1": [
            education(
                "earning degrees from University of Missouri - St. Louis, Drury University, and Missouri State University"
            ),
            jobs(["business and finance", "teacher"], "She has been teaching for 22 years"),
        ],
        "campaign-220674-bio1": [
            education("school at the University of Montana"),
            jobs(
                ["Forest Service smokejumper", "organizer", "union leader"],
                "he went to work for the Forest Service",
            ),
        ],
        "campaign-220751-bio1": [
            office("Andover Select Board", "As an Andover Select Board member"),
            jobs(
                [
                    "White House staff",
                    "Department of Labor chief of staff",
                    "HqO chief operating officer",
                    "Huffington Post chief of staff",
                ],
                "Chief Operating Officer of HqO",
            ),
        ],
        "campaign-220833-bio1": [
            office(
                "County legislator, New York State Assembly, Suffolk County Executive",
                "First elected to public office at just 26",
            ),
            jobs(
                ["television current-events host", "public office and public-authority leadership"],
                "He hosted current events TV shows",
            ),
        ],
        "campaign-220851-bio1": [
            office("New York City Council and Comptroller", "As a City Council Member, Lander"),
            jobs(
                ["nonprofit housing and community-development leadership", "public office"],
                "Brad led two not-for-profit, affordable housing and community development groups",
            ),
        ],
        "campaign-220913-bio1": [
            office("Mayor", "As both a mayor and a business owner"),
            jobs(["business owner"], "As both a mayor and a business owner"),
        ],
        "campaign-220915-home": [
            jobs(
                ["social worker", "professor"], "Kimberly Hardy is a mom, social worker, professor"
            ),
        ],
        "campaign-220925-home": [
            education("I’m a graduate of A.C. Reynolds High School and Warren Wilson College"),
        ],
        "campaign-220940-home": [
            jobs(
                ["military service", "oilfield work", "secondary science teacher"],
                "worked on the oilfield rigs, and taught North Dakota students",
            ),
        ],
        "campaign-220950-bio1": [
            jobs(
                ["high school English teacher", "fast-food work"],
                "worked as a High School English Teacher",
            ),
        ],
        "campaign-220958-home": [
            office(
                "President, Fostoria City Council", "current President of the Fostoria City Council"
            ),
            government(
                "Social studies teacher, Fostoria Junior/Senior High School",
                "teaches social studies at Fostoria Junior/Senior High School",
            ),
        ],
        "campaign-220965-home": [
            office("Brook Park City Council", "Brook Park city councilman"),
            jobs(["union ironworker"], "father, union ironworker"),
        ],
        "campaign-220977-bio1": [
            education("I used my GI Bill funds to attend Ohio University"),
            claim(
                "military",
                {
                    "reported_service": "U.S. Navy flight-deck fueler, meteorologist and oceanographer"
                },
                "join the US Navy where I served as a flight deck fueler",
                timing="undated_retrospective_personal_service_history",
                reason="Explicit first-person service in the directly linked named "
                "candidate's biography; no exact service dates invented.",
            ),
            jobs(
                [
                    "Navy flight-deck fueler",
                    "meteorologist and oceanographer",
                    "outdoor education teacher",
                    "software engineer",
                ],
                "Today, I remain a software engineer",
            ),
        ],
        "campaign-220982-home": [
            office(
                "Former city councilwoman; municipality unspecified", "Former City Councilwoman"
            ),
        ],
        "campaign-220986-bio1": [
            education("I was a post-doc at Tulane University", category=None),
            jobs(["university professor"], "As a professor of city and regional planning"),
            government(
                "Teacher, Ohio State University",
                "For the last ten years, she and I have been blessed to be teachers at Ohio State",
            ),
        ],
        "campaign-221002-bio1": [
            claim(
                "gender",
                {"retrospective_self_description": "boy and young man"},
                "My most formative life experiences as a boy and young man",
                timing="undated_retrospective_self_description",
                reason="Explicit first-person gendered self-description in the named "
                "candidate's biography, not inferred from photographs or relatives. "
                "Retrospective wording is not assigned a current analytical category.",
            ),
            education(
                "earned a Master in Public Administration",
                category="masters",
            ),
            government(
                "USDA national-headquarters policy advisor, beginning 2010 for six years",
                "In 2010 I began working at the U.S. Department of Agriculture’s (USDA) national headquarters as a policy advisor",
            ),
        ],
        "campaign-221146-home": [
            government(
                "Bexar County Sheriff's Deputy and SWAT hostage negotiator, nearly two decades",
                "nearly two decades serving Bexar County as a Sheriff's Deputy and SWAT hostage negotiator",
            ),
        ],
        "campaign-221029-bio1": [
            government(
                "Worked with Pennsylvania Auditor General",
                "Paige worked with the Pennsylvania Auditor General",
                factual=False,
                reason="Work with the Auditor General is explicit, but the statement alone "
                "does not establish paid employment rather than another working relationship.",
            ),
        ],
        "campaign-221045-home": [
            jobs(["engineer"], "Veteran. Engineer. Pro-Union. Pro-Worker."),
        ],
        "campaign-221085-bio1": [
            education("In 2025, I was selected to attend The Campaign School at Yale"),
            jobs(
                ["corporate retail executive", "campaign manager"],
                "In 2022, I began managing political campaigns",
            ),
            claim(
                "religion",
                {"reported_affiliation": "unnamed church community; denomination unspecified"},
                "we’ve built a wonderful community of friends and a loving church family",
                reason="Explicit first-person participation in a church community; no denomination "
                "or Protestant classification inferred, and no dated analytical affiliation.",
            ),
        ],
        "campaign-221101-home": [
            jobs(["businessman"], "As a father, a businessman, and a taxpayer"),
        ],
        "campaign-221121-home": [
            education("he studied political science at St. Mary’s University"),
            jobs(
                ["Tejano recording artist", "business owner"],
                "Bobby has run businesses, created jobs",
            ),
        ],
        "campaign-221135-home": [
            claim(
                "military",
                {"reported_service": "U.S. Marine Corps veteran"},
                "Kevin Burge is a U.S. Marine Corps Veteran",
                reason="Explicit personal service; undated campaign report does not supply "
                "service dates or a nonservice comparison.",
            ),
        ],
        "campaign-221175-home": [
            jobs(
                ["small business owner", "engineer", "congressional work"],
                "Michaela Barnett is a local small business owner and an engineer",
            ),
            government(
                "Congressional work during the preceding year; position unspecified",
                "Michaela Barnett spent last year working in Congress",
                factual=False,
                reason="Congressional work is explicit, but the role and paid-employment "
                "status are unspecified; not automatically a government job.",
            ),
        ],
        "campaign-221185-bio1": [
            claim(
                "religion",
                {
                    "reported_congregational_membership": "Woodmont Christian Church, Nashville; Elder"
                },
                "They are active members of Woodmont Christian Church",
                reason="Explicit candidate church membership and Elder role, not inferred "
                "from a relative; undated and not automatically an analytical denomination.",
            ),
        ],
        "campaign-221191-home": [
            office("Salt Lake County Mayor", "as County Mayor"),
        ],
        "campaign-221269-home": [
            jobs(
                ["small business owner", "nonprofit leader", "campaign work"],
                "she moved back home to Eau Claire to start her own small business",
            ),
        ],
        "campaign-221277-bio1": [
            jobs(
                ["forester", "land manager", "business owner", "organizational executive"],
                "As a forester and land manager",
            ),
            office(
                "Rural legislator; chamber unspecified in this statement", "As a rural legislator"
            ),
        ],
    }
