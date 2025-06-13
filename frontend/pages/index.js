import { useState, useEffect } from 'react'
import axios from 'axios'
import { useRouter } from 'next/router'

function ResumeReviewModal({ resume, onClose }) {
  if (!resume) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
      <div className="bg-white rounded-lg shadow-lg max-w-lg w-full p-6 relative">
        <button className="absolute top-2 right-2 text-gray-500 hover:text-gray-700" onClick={onClose}>&times;</button>
        <h2 className="text-xl font-semibold mb-2">{resume.name}</h2>
        <div className="mb-2 text-sm">
          <span className="font-medium">Email:</span> {resume.email || '-'}<br/>
          <span className="font-medium">Phone:</span> {resume.phone || '-'}<br/>
          <span className="font-medium">Total Experience:</span> {resume.total_experience || '-'} years<br/>
          <span className="font-medium">Relevant Experience:</span> {resume.relevant_experience || '-'} years<br/>
          <span className="font-medium">AI Score:</span> {resume.ai_score !== undefined && resume.ai_score !== null ? resume.ai_score : '-'}
        </div>
        <div className="mt-4">
          <h3 className="font-medium mb-1">AI Review:</h3>
          {resume.review ? (
            <pre className="whitespace-pre-wrap bg-gray-100 p-2 rounded text-sm max-h-60 overflow-y-auto">{resume.review}</pre>
          ) : (
            <div className="text-gray-500 mt-2">No review available yet</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [jd, setJd] = useState('')
  const [jdTitle, setJdTitle] = useState('')
  const [numShortlist, setNumShortlist] = useState('')
  const [applicationDeadline, setApplicationDeadline] = useState('')
  const [resumes, setResumes] = useState([])
  const [results, setResults] = useState([])
  const [jdList, setJdList] = useState([])
  const [selectedJdId, setSelectedJdId] = useState(null)
  const [selectedJdText, setSelectedJdText] = useState('')
  const [selectedResume, setSelectedResume] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [reviewModalResume, setReviewModalResume] = useState(null)
  const [selectionType, setSelectionType] = useState('FIXED')
  const [showTopApplicants, setShowTopApplicants] = useState(false)
  const [sortField, setSortField] = useState('');
  const [sortOrder, setSortOrder] = useState('desc'); // 'asc' or 'desc'
  const [step, setStep] = useState(1); // 1: JD select/create, 2: JD actions
  const router = useRouter();

  useEffect(() => {
    fetchJdList();
    const params = new URLSearchParams(window.location.search);
    const jdIdParam = params.get('jd_id');
    if (jdIdParam) {
      const jdId = parseInt(jdIdParam);
      setSelectedJdId(jdId);
      fetchJdDetails(jdId);
      fetchResumes(jdId);
      setStep(2);
    }
  }, []);

  const fetchJdList = async () => {
    try {
      const res = await axios.get('http://localhost:8000/list_jds')
      setJdList(res.data.jds)
    } catch (error) {
      console.error("Failed to fetch JD list:", error)
    }
  }

  const fetchJdDetails = async (jdId) => {
    try {
      const res = await axios.get(`http://localhost:8000/jd_details?jd_id=${jdId}`)
      setSelectedJdText(res.data.text)
      setNumShortlist(res.data.num_shortlist || '')
      setApplicationDeadline(res.data.application_deadline ? res.data.application_deadline.substring(0, 10) : '')
      setSelectionType(res.data.selectionType || 'FIXED')
    } catch (error) {
      console.error("Failed to fetch JD details:", error)
    }
  }

  const fetchResumes = async (jdId) => {
    try {
      const res = await axios.get(`http://localhost:8000/list_resumes?jd_id=${jdId}`)
      setResumes(res.data.resumes)
    } catch (error) {
      console.error("Failed to fetch resumes:", error)
    }
  }

  const fetchResumeDetails = async (resumeId) => {
    setIsLoading(true)
    try {
      const res = await axios.get(`http://localhost:8000/resume_details?resume_id=${resumeId}`)
      setSelectedResume(res.data)
    } catch (error) {
      console.error("Failed to fetch resume details:", error)
      alert('Error fetching resume details')
    } finally {
      setIsLoading(false)
    }
  }

  const handleJDSubmit = async () => {
    if (!jdTitle.trim()) {
      alert('Please enter a job title')
      return
    }
    try {
      const formData = new URLSearchParams()
      formData.append('text', jd)
      formData.append('name', jdTitle)
      if (numShortlist) formData.append('num_shortlist', numShortlist)
      if (applicationDeadline) formData.append('application_deadline', applicationDeadline)
      if (selectionType) formData.append('selectionType', selectionType)
      const res = await axios.post('http://localhost:8000/upload_jd', formData)
      setSelectedJdId(res.data.jd_id)
      setSelectedJdText(jd)
      setResumes([])
      setSelectedResume(null)
      alert('JD uploaded!')
      fetchJdList()
      setStep(2)
      router.replace(`/?jd_id=${res.data.jd_id}`, undefined, { shallow: true });
    } catch (error) {
      console.error("Failed to upload JD:", error)
      alert('Error uploading JD')
    }
  }

  const handleResumeUpload = async (e) => {
    if (!selectedJdId) {
      alert('Please select a JD first')
      return
    }
    const files = e.target.files
    for (let file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('jd_id', selectedJdId)
      try {
        await axios.post('http://localhost:8000/upload_resume', formData)
        // No AI review/score set here
      } catch (error) {
        console.error("Failed to upload resume:", error)
        alert(`Error uploading resume: ${file.name}`)
      }
    }
    fetchResumes(selectedJdId)
  }

  const handleStartRanking = async () => {
    if (!selectedJdId) {
      alert('Please select a JD first')
      return
    }
    setIsLoading(true)
    try {
      await axios.post(`http://localhost:8000/start_ranking?jd_id=${selectedJdId}`)
      await fetchResumes(selectedJdId)
      alert('Ranking complete!')
    } catch (error) {
      alert('Error running AI ranking')
    } finally {
      setIsLoading(false)
    }
  }

  const handleContactTopApplicants = async () => {
    if (!selectedJdId) return;
    setIsLoading(true);
    try {
      await axios.post(`http://localhost:8000/contact_top_applicants?jd_id=${selectedJdId}`);
      alert('WhatsApp messages sent!');
    } catch (e) {
      alert('Failed to send WhatsApp messages');
    } finally {
      setIsLoading(false);
    }
  };

  const handleJdSelect = (e) => {
    const jdId = parseInt(e.target.value)
    setSelectedJdId(jdId)
    setSelectedResume(null)
    if (jdId) {
      fetchJdDetails(jdId)
      fetchResumes(jdId)
      setStep(2)
      router.replace(`/?jd_id=${jdId}`, undefined, { shallow: true });
    } else {
      setSelectedJdText('')
      setResumes([])
      router.replace('/', undefined, { shallow: true });
    }
  }

  const handleResumeNameClick = async (resumeId) => {
    setIsLoading(true)
    try {
      const res = await axios.get(`http://localhost:8000/resume_details?resume_id=${resumeId}`)
      setReviewModalResume(res.data)
    } catch (error) {
      alert('Error fetching resume details')
    } finally {
      setIsLoading(false)
    }
  }

  // Compute filtered resumes based on toggle and JD settings
  let displayedResumes = resumes;
  const numShort = parseInt(numShortlist) || 0;
  if (showTopApplicants && resumes.length > 0 && numShort > 0) {
    // Only consider resumes with a valid ai_score
    const scored = resumes.filter(r => typeof r.ai_score === 'number');
    const sorted = [...scored].sort((a, b) => b.ai_score - a.ai_score);
    if (selectionType === 'FIXED') {
      displayedResumes = sorted.slice(0, numShort);
    } else if (selectionType === 'PERCENTAGE') {
      const n = Math.max(1, Math.floor((numShort / 100) * resumes.length));
      displayedResumes = sorted.slice(0, n);
    }
  }
  // Add sorting logic
  if (sortField) {
    displayedResumes = [...displayedResumes].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];
      if (aVal === undefined || aVal === null) aVal = -Infinity;
      if (bVal === undefined || bVal === null) bVal = -Infinity;
      if (sortOrder === 'asc') return aVal - bVal;
      return bVal - aVal;
    });
  }

  return (
    <div className="max-w-4xl mx-auto py-10 px-4">
      <h1 className="text-3xl font-bold mb-4">Resume Shortlister</h1>
      {step === 1 ? (
        <div>
          <h2 className="text-lg font-semibold mb-2">Select Existing JD:</h2>
          <select 
            className="border p-2 rounded w-full mb-2"
            onChange={handleJdSelect}
            value={selectedJdId || ""}
          >
            <option value="">-- Select a JD --</option>
            {jdList.map(jd => (
              <option key={jd.id} value={jd.id}>
                {jd.name} - {new Date(jd.created_at).toLocaleString()}
              </option>
            ))}
          </select>
          <div className="my-6 border-t pt-6">
            <h2 className="text-lg font-semibold mb-2">Or Create New JD:</h2>
            <input
              type="text"
              className="w-full border p-2 rounded mb-4"
              placeholder="Job Title (e.g., SDE-1, Engineering Manager)"
              value={jdTitle}
              onChange={(e) => setJdTitle(e.target.value)}
            />
            <select
              className="w-full border p-2 rounded mb-4"
              value={selectionType}
              onChange={e => setSelectionType(e.target.value)}
            >
              <option value="FIXED">FIXED</option>
              <option value="PERCENTAGE">PERCENTAGE</option>
            </select>
            <input
              type="number"
              className="w-full border p-2 rounded mb-4"
              placeholder="How many people to shortlist?"
              value={numShortlist}
              onChange={e => setNumShortlist(e.target.value)}
              min={1}
            />
            <input
              type="date"
              className="w-full border p-2 rounded mb-4"
              placeholder="Application Deadline"
              value={applicationDeadline}
              onChange={e => setApplicationDeadline(e.target.value)}
            />
            <textarea
              className="w-full border p-2 rounded mb-4"
              rows={6}
              placeholder="Paste Job Description here..."
              value={jd}
              onChange={(e) => setJd(e.target.value)}
            ></textarea>
            <button
              className="bg-blue-600 text-white px-4 py-2 rounded mb-4"
              onClick={handleJDSubmit}
            >
              Upload JD
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* JD Details Header */}
          {selectedJdText && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-2">Job Description:</h2>
              <div className="border p-3 rounded bg-gray-50 text-sm whitespace-pre-wrap max-h-40 overflow-y-auto mb-2">
                {selectedJdText}
              </div>
              <div className="flex flex-wrap gap-4 text-sm">
                {numShortlist && (
                  <div><span className="font-medium">Shortlist Count:</span> {numShortlist}</div>
                )}
                {applicationDeadline && (
                  <div><span className="font-medium">Deadline:</span> {applicationDeadline}</div>
                )}
                {selectionType && (
                  <div><span className="font-medium">Selection Type:</span> {selectionType}</div>
                )}
              </div>
            </div>
          )}
          {/* Resume Management UI (step 2) */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-2">Upload Resumes:</h2>
            <input
              type="file"
              multiple
              accept="application/pdf"
              onChange={handleResumeUpload}
              className="mb-4"
              disabled={!selectedJdId}
            />
            <button
              className="bg-yellow-600 text-white px-4 py-2 rounded mb-4 ml-4"
              onClick={handleStartRanking}
              disabled={!selectedJdId || isLoading}
            >
              {isLoading ? 'Ranking...' : 'Start Ranking'}
            </button>
            <button
              className="bg-green-700 text-white px-4 py-2 rounded mb-4 ml-4"
              onClick={handleContactTopApplicants}
              disabled={!selectedJdId || isLoading}
            >
              {isLoading ? 'Contacting...' : 'Contact Top Applicants'}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-3">
              <div className="mb-6">
                <div className="flex items-center mb-2">
                  <h2 className="text-lg font-semibold mr-4">Uploaded Resumes:</h2>
                  <label className="flex items-center space-x-2 cursor-pointer mr-4">
                    <input
                      type="checkbox"
                      checked={showTopApplicants}
                      onChange={e => setShowTopApplicants(e.target.checked)}
                      className="form-checkbox h-4 w-4 text-blue-600"
                    />
                    <span className="text-sm">Show top applicants only</span>
                  </label>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm">Sort by:</span>
                    <select
                      className="border p-1 rounded text-sm"
                      value={sortField}
                      onChange={e => setSortField(e.target.value)}
                    >
                      <option value="">None</option>
                      <option value="total_experience">Total Exp</option>
                      <option value="relevant_experience">Relevant Exp</option>
                      <option value="ai_score">AI Score</option>
                    </select>
                    <button
                      className="border rounded px-2 py-1 text-sm bg-gray-100"
                      onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                      title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
                    >
                      {sortOrder === 'asc' ? '↑' : '↓'}
                    </button>
                  </div>
                </div>
                {displayedResumes.length === 0 ? (
                  <div className="text-gray-500">No resumes uploaded yet.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full border rounded text-sm">
                      <thead className="bg-gray-100">
                        <tr>
                          <th className="p-2 border">Name</th>
                          <th className="p-2 border">Email</th>
                          <th className="p-2 border">Phone</th>
                          <th className="p-2 border">Total Exp</th>
                          <th className="p-2 border">Relevant Exp</th>
                          <th className="p-2 border">AI Score</th>
                          <th className="p-2 border">Download</th>
                        </tr>
                      </thead>
                      <tbody>
                        {displayedResumes.map((res) => (
                          <tr key={res.id} className="hover:bg-gray-50">
                            <td className="p-2 border text-blue-700 cursor-pointer underline" onClick={() => handleResumeNameClick(res.id)}>{res.name}</td>
                            <td className="p-2 border">{res.email || '-'}</td>
                            <td className="p-2 border">{res.phone || '-'}</td>
                            <td className="p-2 border">{res.total_experience !== undefined ? res.total_experience : '-'}</td>
                            <td className="p-2 border">{res.relevant_experience !== undefined ? res.relevant_experience : '-'}</td>
                            <td className="p-2 border">{res.ai_score !== undefined && res.ai_score !== null ? res.ai_score : '-'}</td>
                            <td className="p-2 border text-center">
                              <a href={`http://localhost:8000/download_resume/${res.id}`} target="_blank" rel="noopener noreferrer" title="Download Resume" className="text-blue-600 hover:text-blue-800">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 inline" viewBox="0 0 20 20" fill="currentColor">
                                  <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                                </svg>
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
            <div className="md:col-span-2">
              {selectedResume ? (
                <div className="border p-4 rounded shadow">
                  <div className="flex justify-between items-center">
                    <h2 className="text-xl font-semibold">{selectedResume.name}</h2>
                    <a 
                      href={`http://localhost:8000/download_resume/${selectedResume.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:text-blue-800"
                      title="Download Resume"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                    </a>
                  </div>
                  
                  <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                    {selectedResume.email && (
                      <div className="col-span-1">
                        <span className="font-medium">Email:</span> {selectedResume.email}
                      </div>
                    )}
                    {selectedResume.phone && (
                      <div className="col-span-1">
                        <span className="font-medium">Phone:</span> {selectedResume.phone}
                      </div>
                    )}
                    {selectedResume.linkedin && (
                      <div className="col-span-1">
                        <span className="font-medium">LinkedIn:</span> {selectedResume.linkedin}
                      </div>
                    )}
                    {selectedResume.location && (
                      <div className="col-span-1">
                        <span className="font-medium">Location:</span> {selectedResume.location}
                      </div>
                    )}
                    {selectedResume.total_experience !== undefined && (
                      <div className="col-span-1">
                        <span className="font-medium">Total Experience:</span> {selectedResume.total_experience} years
                      </div>
                    )}
                    {selectedResume.relevant_experience !== undefined && (
                      <div className="col-span-1">
                        <span className="font-medium">Relevant Experience:</span> {selectedResume.relevant_experience} years
                      </div>
                    )}
                    {selectedResume.ai_score !== undefined && selectedResume.ai_score !== null && (
                      <div className="col-span-1">
                        <span className="font-medium">AI Score:</span> {selectedResume.ai_score}
                      </div>
                    )}
                  </div>
                  
                  <div className="mt-4">
                    <h3 className="font-medium mb-1">AI Review:</h3>
                    {isLoading ? (
                      <div className="text-center py-4">Loading review...</div>
                    ) : selectedResume.review ? (
                      <pre className="whitespace-pre-wrap bg-gray-100 p-2 rounded text-sm">{selectedResume.review}</pre>
                    ) : (
                      <div className="text-gray-500 mt-2">No review available yet</div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          <button
            className="mt-8 text-blue-600 underline"
            onClick={() => {
              setStep(1);
              router.replace('/', undefined, { shallow: true });
            }}
          >
            &larr; Back to JD Selection
          </button>
        </>
      )}
      {reviewModalResume && (
        <ResumeReviewModal resume={reviewModalResume} onClose={() => setReviewModalResume(null)} />
      )}
    </div>
  )
} 