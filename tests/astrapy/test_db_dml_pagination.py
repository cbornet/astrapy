# Copyright DataStax, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for the `db.py` parts on pagination primitives
"""

import math
import os
import logging
from typing import Dict, Iterable, List, Optional, Set, TypeVar
import pytest

from astrapy.db import AstraDB, AstraDBCollection


logger = logging.getLogger(__name__)


TEST_PAGINATION_COLLECTION_NAME = "pagination_v_col"
INSERT_BATCH_SIZE = 20  # max 20, fixed by API constraints
N = 200  # must be EVEN
FIND_LIMIT = 183  # Keep this > 20 and <= N to actually put pagination to test

T = TypeVar("T")


def _mk_vector(index: int, n_total_steps: int) -> List[float]:
    angle = 2 * math.pi * index / n_total_steps
    return [math.cos(angle), math.sin(angle)]


def _batch_iterable(iterable: Iterable[T], batch_size: int) -> Iterable[Iterable[T]]:
    this_batch = []
    for entry in iterable:
        this_batch.append(entry)
        if len(this_batch) == batch_size:
            yield this_batch
            this_batch = []
    if this_batch:
        yield this_batch


@pytest.fixture(scope="module")
def pag_test_collection(
    astra_db_credentials_kwargs: Dict[str, Optional[str]]
) -> Iterable[AstraDBCollection]:
    astra_db = AstraDB(**astra_db_credentials_kwargs)

    astra_db_collection = astra_db.create_collection(
        collection_name=TEST_PAGINATION_COLLECTION_NAME, dimension=2
    )

    if int(os.getenv("TEST_PAGINATION_SKIP_INSERTION", "0")) == 0:
        inserted_ids: Set[str] = set()
        for i_batch in _batch_iterable(range(N), INSERT_BATCH_SIZE):
            batch_ids = astra_db_collection.insert_many(
                documents=[
                    {"_id": str(i), "$vector": _mk_vector(i, N)} for i in i_batch
                ]
            )["status"]["insertedIds"]
            inserted_ids = inserted_ids | set(batch_ids)
        assert inserted_ids == {str(i) for i in range(N)}
    yield astra_db_collection
    if int(os.getenv("TEST_PAGINATION_SKIP_DELETE_COLLECTION", "0")) == 0:
        _ = astra_db.delete_collection(collection_name=TEST_PAGINATION_COLLECTION_NAME)


@pytest.mark.describe(
    "should retrieve the required amount of documents, all different, through pagination"
)
def test_find_paginated(pag_test_collection: AstraDBCollection) -> None:
    options = {"limit": FIND_LIMIT}
    projection = {"$vector": 0}

    paginated_documents = pag_test_collection.paginated_find(
        projection=projection,
        options=options,
    )
    paginated_ids = [doc["_id"] for doc in paginated_documents]
    assert len(paginated_ids) == FIND_LIMIT
    assert len(paginated_ids) == len(set(paginated_ids))
