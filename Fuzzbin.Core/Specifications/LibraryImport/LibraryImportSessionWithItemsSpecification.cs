using System;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications;

namespace Fuzzbin.Core.Specifications.LibraryImport
{
    public class LibraryImportSessionWithItemsSpecification : BaseSpecification<LibraryImportSession>
    {
        public LibraryImportSessionWithItemsSpecification(Guid sessionId)
            : base(session => session.Id == sessionId)
        {
            AddInclude(session => session.Items);
        }
    }
}
