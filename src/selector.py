import random
import logging
from .collector import Domain, Article

logger = logging.getLogger(__name__)


class DomainSelector:
    def __init__(self, select_count: int = 3):
        self.select_count = select_count

    def select(self, domains: list[Domain]) -> list[tuple[Domain, Article]]:
        eligible = [(d, art) for d in domains for art in d.articles]
        if not eligible:
            logger.warning("No articles available for selection")
            return []

        by_domain: dict[str, list[tuple[Domain, Article]]] = {}
        for d, art in eligible:
            by_domain.setdefault(d.name, []).append((d, art))

        domain_names = list(by_domain.keys())
        random.shuffle(domain_names)

        weights = []
        for name in domain_names:
            w = by_domain[name][0][0].weight
            inv_weight = 1.0 / max(w, 1)
            weights.append(inv_weight)

        count = min(self.select_count, len(domain_names))
        selected_domains = random.choices(domain_names, weights=weights, k=count)

        seen: set[str] = set()
        unique_domains = []
        for name in selected_domains:
            if name not in seen:
                seen.add(name)
                unique_domains.append(name)

        while len(unique_domains) < count:
            remaining = [n for n in domain_names if n not in seen]
            if not remaining:
                break
            extra = random.choices(remaining, k=1)[0]
            seen.add(extra)
            unique_domains.append(extra)

        picked: list[tuple[Domain, Article]] = []
        for name in unique_domains[:count]:
            candidates = by_domain[name]
            article = random.choice(candidates)
            picked.append(article)
            logger.info(f"Selected: [{article[0].icon} {name}] {article[1].title[:60]}...")

        return picked