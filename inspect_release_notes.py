import requests
from bs4 import BeautifulSoup

def inspect():
    resp = requests.get("https://www.figma.com/release-notes/")
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # Find all articles or divs that look like entries
    # Usually they have a date and a title
    
    print("\n--- Headers ---")
    for tag in soup.find_all(["h2", "h3"]):
        print(f"Tag: {tag.name}, Text: {tag.get_text(strip=True)}, Class: {tag.get('class')}")
        parent = tag.find_parent("div")
        if parent:
            print(f"  Parent Class: {parent.get('class')}")
            
    print("\n--- Links with dates? ---")
    # Sometimes dates are in time tags or spans
    for tag in soup.find_all("time"):
        print(f"Time: {tag.get_text(strip=True)}, Parent: {tag.parent.name} {tag.parent.get('class')}")

if __name__ == "__main__":
    inspect()
