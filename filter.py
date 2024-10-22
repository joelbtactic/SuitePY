import enum

class Comparison(enum.Enum):
   EQ = 1
   NEQ = 2
   GT = 3
   GTE = 4
   LT = 5
   LTE = 6
   LIKE = 7
   NOTLIKE = 8

class Logical(enum.Enum):
    AND = 1
    OR = 2

class FilterTriplet:

    def __init__(self, comparison, field, criteria):
        """
        Constructor for a filter triplet
        :param comparison: Comparison type based on the enum Comparison
        :param field string: The field for the filter e.g. name
        :param criteria: The criteria for the filter e.g. 6 or test
        """
        if not isinstance(comparison, Comparison):
            raise TypeError("comparison parameter has to be of type enum Comparison")

        self._comparison = comparison
        self._field = field
        self._criteria = criteria
    
    def to_filter_string(self):
        return "filter[{0}][{1}][]={2}".format(self._field, self._comparison.name.lower(), self._criteria)

class Filter:

    def __init__(self, logical, criteria):
        """
        Constructor for the filter
        :param logical: The logical connector. Must be of enum Logical
        :param criteria list: List of criterias of FilterTriplet
        """
        if not isinstance(logical, Logical):
            raise TypeError("logical parameter has to be of type enum Logical")

        self._logical = logical
        self._criteria = criteria
    
    def to_filter_string(self):
        criteria_string = ""
        for c in self._criteria:
            criteria_string += "&{0}".format(c.to_filter_string())

        return "filter[operator]={0}{1}".format(self._logical.name.lower(), criteria_string)
    
def from_legacy_query(legacy_query):
    """
    Create a Filter object from a legacy query string.

    :param legacy_query str: The legacy query string to be translated.
    :returns Filter: A Filter object representing the translated query.
    """
    comparison_sym = {
        "=": Comparison.EQ,
        "!=": Comparison.NEQ,
        ">": Comparison.GT,
        ">=": Comparison.GTE,
        "<": Comparison.LT,
        "<=": Comparison.LTE,
        "like": Comparison.LIKE,
        "notlike": Comparison.NOTLIKE
    }

    query = []

    # Split the legacy query string into parts
    logical = Logical.AND
    parts = legacy_query.split(" AND ")

    if " OR " in legacy_query:
        logical = Logical.OR
        parts = legacy_query.split(" OR ")
    
    for part in parts:
        # Split each part into field, comparison, and criteria
        if "notlike" in part:
            field, criteria = part.split(" notlike ")
            comparison_enum = comparison_sym["notlike"]

        elif "like" in part:
            field, criteria = part.split(" like ")
            comparison_enum = comparison_sym["like"]

        else:
            field, comparison, criteria = part.split()
            comparison_enum = comparison_sym[comparison]

        # Clean up criteria
        criteria = criteria.strip("'")
        # Extract the field name from the legacy query
        field = field.split(".")[1]

        # Create a FilterTriplet and add it to the criteria list
        criteria_obj = FilterTriplet(comparison_enum, field, criteria)
        query.append(criteria_obj)

    # Create and return a Filter object
    return Filter(logical, query)
