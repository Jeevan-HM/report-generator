"""
Google Gemini AI Integration Module
Provides AI-powered analysis for inspection reports with minimal API usage.
"""

import os
from typing import Dict, List, Optional

import google.generativeai as genai

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class GeminiAnalyzer:
    """Smart AI analyzer that minimizes API calls while maximizing value."""

    def __init__(self):
        """Initialize Gemini with Flash model (fastest, free tier)."""
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.enabled = bool(GEMINI_API_KEY)

    def is_enabled(self) -> bool:
        """Check if Gemini is configured and enabled."""
        return self.enabled

    async def generate_executive_summary(self, inspection_data: Dict) -> Optional[str]:
        """
        Generate a concise executive summary of the entire inspection.
        Single API call per report.

        Returns:
            Brief 2-3 paragraph summary highlighting key findings
        """
        if not self.enabled:
            return None

        try:
            # Extract key information
            address = inspection_data.get("inspection", {}).get("address", {})
            full_address = address.get("fullAddress", "Unknown Address")

            sections = inspection_data.get("inspection", {}).get("sections", [])

            # Count deficiencies and critical items (without analyzing comments)
            total_items = 0
            deficient_items = 0
            deficient_by_section = {}

            for section in sections:
                section_name = section.get("name", "")
                section_deficiencies = []

                # Get lineItems directly from section
                line_items = section.get("lineItems", [])
                for item in line_items:
                    total_items += 1
                    if item.get("isDeficient", False):
                        deficient_items += 1
                        section_deficiencies.append(
                            {
                                "item": item.get("name", ""),
                                "title": item.get("title", ""),
                            }
                        )

                if section_deficiencies:
                    deficient_by_section[section_name] = section_deficiencies

            # Create prompt for Gemini (concise to save tokens)
            prompt = f"""Analyze this property inspection and provide a brief executive summary (2-3 paragraphs, max 150 words):

Property: {full_address}
Total Items Inspected: {total_items}
Items with Deficiencies: {deficient_items}

Deficient Items by Section:
{self._format_deficiencies_summary(deficient_by_section)}

Provide:
1. Overall property condition assessment based on the number and types of deficiencies
2. Top 3 priority areas/sections with issues
3. General recommendation (move-in ready, minor repairs needed, major concerns, etc.)

Keep it professional, concise, and actionable for homebuyers. Base your analysis on the inspection structure, not specific comments."""

            response = self.model.generate_content(prompt)
            return response.text.strip()

        except Exception as e:
            print(f"Gemini API Error (summary): {e}")
            return None

    async def analyze_deficiencies(self, inspection_data: Dict) -> Optional[Dict]:
        """
        Analyze all deficiencies and provide prioritized recommendations.
        Single API call per report.

        Returns:
            Dictionary with categorized deficiencies (safety, urgent, routine)
        """
        if not self.enabled:
            return None

        try:
            sections = inspection_data.get("inspection", {}).get("sections", [])

            # Collect all deficient items (without comments)
            deficiencies = []
            for section in sections:
                section_name = section.get("name", "")
                # Get lineItems directly from section
                line_items = section.get("lineItems", [])
                for item in line_items:
                    if item.get("isDeficient", False):
                        deficiencies.append(
                            {
                                "section": section_name,
                                "item": item.get("name", ""),
                                "title": item.get("title", ""),
                            }
                        )

            if not deficiencies:
                return {"safety": [], "urgent": [], "routine": []}

            # Batch analyze (limit to 30 most important to save tokens)
            prompt = f"""Categorize these {len(deficiencies)} property inspection deficiencies into:
1. SAFETY (immediate safety hazards - electrical, structural, fire hazards, etc.)
2. URGENT (needs attention within 30 days - water damage, HVAC issues, major repairs)  
3. ROUTINE (can wait 30+ days - cosmetic issues, minor maintenance)

Deficiencies (by section and item name only):
{self._format_deficiencies_for_categorization(deficiencies[:30])}

Respond ONLY with JSON format:
{{"safety": ["Section - Item"], "urgent": ["Section - Item"], "routine": ["Section - Item"]}}

Use format "Section - Item" for each entry. Base categorization on the item names and section context, not on specific comment details."""

            response = self.model.generate_content(prompt)

            # Parse response (simple JSON extraction)
            import json
            import re

            json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            return None

        except Exception as e:
            print(f"Gemini API Error (deficiencies): {e}")
            return None

    def enhance_summary_insights_sync(
        self, deficiency_analysis: Optional[Dict], executive_summary: Optional[str]
    ) -> Dict:
        """
        Combine AI analysis results for the report.
        No additional API calls - just formatting.
        Synchronous version for use without event loop.
        """
        insights = {
            "has_ai_analysis": bool(executive_summary or deficiency_analysis),
            "executive_summary": executive_summary or "",
            "deficiency_categories": deficiency_analysis or {},
        }

        # Generate a quick bullet-point version if we have data
        if deficiency_analysis:
            safety_count = len(deficiency_analysis.get("safety", []))
            urgent_count = len(deficiency_analysis.get("urgent", []))
            routine_count = len(deficiency_analysis.get("routine", []))

            insights["priority_summary"] = (
                f"• {safety_count} Safety Concern{'s' if safety_count != 1 else ''}\n"
                f"• {urgent_count} Urgent Issue{'s' if urgent_count != 1 else ''}\n"
                f"• {routine_count} Routine Maintenance Item{'s' if routine_count != 1 else ''}"
            )

        return insights

    async def enhance_summary_insights(
        self, deficiency_analysis: Optional[Dict], executive_summary: Optional[str]
    ) -> Dict:
        """
        Async wrapper for enhance_summary_insights_sync.
        Kept for backward compatibility.
        """
        return self.enhance_summary_insights_sync(
            deficiency_analysis, executive_summary
        )

    def _format_deficiencies_summary(self, deficient_by_section: dict) -> str:
        """Format deficiencies by section for executive summary."""
        if not deficient_by_section:
            return "No deficiencies found."

        formatted = []
        for section_name, items in deficient_by_section.items():
            item_names = [f"{item['item']}" for item in items[:5]]  # Limit to top 5
            formatted.append(
                f"• {section_name} ({len(items)} items): {', '.join(item_names)}"
            )

        return "\n".join(formatted[:10])  # Limit to top 10 sections

    def _format_deficiencies_for_categorization(self, deficiencies: list) -> str:
        """Format deficiencies for categorization (without comments)."""
        formatted = []
        for i, d in enumerate(deficiencies, 1):
            item_name = d.get("title") or d.get("item", "Unknown Item")
            formatted.append(f"{i}. {d['section']} - {item_name}")
        return "\n".join(formatted)


# Singleton instance
_analyzer = None


def get_gemini_analyzer() -> GeminiAnalyzer:
    """Get or create the Gemini analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = GeminiAnalyzer()
    return _analyzer
